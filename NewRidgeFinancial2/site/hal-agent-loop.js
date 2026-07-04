/**
 * HAL agent loop — Cursor-style model-driven tool rounds, patch apply, validate retry.
 */
(function (global) {
  "use strict";

  const VERSION = "agent-loop-v3";
  let MAX_LOOP_TURNS = 6;
  let MAX_TOOLS_PER_TURN = 3;
  const MAX_VALIDATE_RETRIES = 2;

  function configureFromAgentProgramming(ap) {
    const cfg = ap || {};
    if (typeof cfg.maxToolsPerTurn === "number" && cfg.maxToolsPerTurn > 0) {
      MAX_TOOLS_PER_TURN = Math.min(8, Math.max(1, cfg.maxToolsPerTurn));
    }
    if (typeof cfg.agentLoopMaxTurns === "number" && cfg.agentLoopMaxTurns > 0) {
      MAX_LOOP_TURNS = Math.min(10, Math.max(2, cfg.agentLoopMaxTurns));
    }
  }

  const TOOL_LOOP_GUIDE = [
    "AGENT TOOL LOOP (internal protocol):",
    "When you need more evidence before answering, output one or more tool blocks ONLY (no staff answer yet):",
    "<<<tool",
    "name: tool_id",
    "query: arguments or search terms",
    ">>>",
    "Allowed tool ids include: grep_program_source, read_program_file, semantic_search_program, read_import_diagnostics, read_widget_feed, read_program_snapshot, run_hal_validation, run_node_syntax_check, run_command, run_git_readonly, spawn_investigation, explain_route, read_program_help.",
    "For run_command use query: validate-hal | node-check-agent | node-check-app | git-status.",
    "After tool results appear in context, either request more tools or write the final staff-facing answer (no <<<tool blocks in the final answer).",
    "To propose code changes, include <<<patch blocks; they may be applied automatically when task completion is enabled.",
  ].join("\n");

  function normalizeToolId(id) {
    const map = {
      run_git_status: "run_git_readonly",
      git_status: "run_git_readonly",
      semantic_search: "semantic_search_program",
    };
    return map[id] || id;
  }

  function parseCloudToolCalls(toolCalls) {
    return (toolCalls || []).slice(0, MAX_TOOLS_PER_TURN).map((tc) => {
      const fn = tc && tc.function ? tc.function : {};
      let name = String(fn.name || "").trim().replace(/\s+/g, "_");
      let query = "";
      try {
        const argsRaw = fn.arguments;
        const args =
          typeof argsRaw === "string"
            ? JSON.parse(String(argsRaw || "{}"))
            : argsRaw && typeof argsRaw === "object"
              ? argsRaw
              : {};
        query = args.query || args.command || args.command_id || "";
      } catch {
        query = String(fn.arguments || "").slice(0, 500);
      }
      return { name: normalizeToolId(name), query };
    });
  }

  function parseToolRequests(text) {
    const blocks = [];
    const re = /<<<tool\s+([\s\S]*?)>>>/gi;
    let m;
    while ((m = re.exec(String(text || ""))) !== null) {
      const body = m[1];
      const nameMatch = body.match(/^\s*name:\s*(.+)$/im);
      const queryMatch = body.match(/^\s*query:\s*([\s\S]*)$/im);
      if (!nameMatch) continue;
      let name = nameMatch[1].trim().replace(/\s+/g, "_");
      if (name === "run_git_status") name = "run_git_readonly";
      blocks.push({ name, query: queryMatch ? queryMatch[1].trim() : "" });
    }
    return blocks.slice(0, MAX_TOOLS_PER_TURN);
  }

  function parseAllPatches(text) {
    const patches = [];
    const re = /<<<patch\s+([\s\S]*?)>>>/gi;
    let m;
    while ((m = re.exec(String(text || ""))) !== null) {
      const body = m[1];
      const fileMatch = body.match(/^\s*file:\s*(.+)$/im);
      const oldMatch = body.match(/^\s*old:\s*\n([\s\S]*?)(?=^\s*new:\s*\n)/im);
      const newMatch = body.match(/^\s*new:\s*\n([\s\S]*)$/im);
      if (fileMatch && oldMatch && newMatch) {
        patches.push({
          file: fileMatch[1].trim(),
          old: oldMatch[1].replace(/\r\n/g, "\n"),
          new: newMatch[1].replace(/\r\n/g, "\n"),
        });
      }
    }
    return patches;
  }

  function stripToolBlocks(text) {
    return String(text || "")
      .replace(/<<<tool[\s\S]*?>>>/gi, "")
      .trim();
  }

  function shouldUseAgentLoop(query, route, plan, cfg) {
    if (!plan || !plan.useModelEnhancement) return false;
    if (cfg && cfg.agentToolLoop === false) return false;
    if (/<<<tool/i.test(query)) return true;
    if (plan.agentToolLoop) return true;
    if (plan.isTaskCompletionQuery) return true;
    if (plan.isInvestigateQuery) return true;
    if (/(how does|why is|fix|debug|investigate|validate|patch|source code|grep|where is .* handled)/i.test(query)) {
      return true;
    }
    return !!(plan.tools && plan.tools.length > 2);
  }

  function ranToolKeys(toolResults) {
    const ran = new Set();
    Object.keys(toolResults || {}).forEach((k) => {
      ran.add(k.replace(/_L\d+$/, "").replace(/^apply_/, ""));
    });
    return ran;
  }

  function suggestAutoTools(query, plan, toolResults, toolIds, cfg) {
    if (cfg && cfg.agentAutoTools === false) return [];
    const ran = ranToolKeys(toolResults);
    const out = [];
    const q = String(query || "");
    const add = (name, subq) => {
      const id = normalizeToolId(name);
      if (toolIds && !toolIds.has(id)) return;
      if (ran.has(id)) return;
      out.push({ name: id, query: subq || q });
      ran.add(id);
    };

    if (/how|code|function|handled|route|grep|source|bug|fix|implement|patch|where is|what does/i.test(q)) {
      add("grep_program_source", q);
      add("semantic_search_program", q);
    }
    if (/import|widget|empty|missing|stale|feed/i.test(q)) {
      add("read_import_diagnostics", q);
      add("read_widget_feed", q);
    }
    if (/\bvalidate|validation|make.*pass\b/i.test(q)) add("run_hal_validation", q);
    if (/\bvalidate|validation|make.*pass\b/i.test(q)) add("run_command", "validate-hal");
    if (/\bgit\b|changed files|diff|commit/i.test(q)) add("run_git_readonly", q);
    if (plan && (plan.isInvestigateQuery || plan.isTaskCompletionQuery)) {
      add("read_program_snapshot", q);
      add("grep_program_source", q);
    }
    if (plan && plan.isInvestigateQuery && /deep|trace|step|multiple|why|how does/i.test(q)) {
      add("spawn_investigation", q);
    }
    add("read_current_context", q);
    if (!ran.has("read_program_snapshot")) add("read_program_snapshot", q);
    return out.slice(0, MAX_TOOLS_PER_TURN);
  }

  async function executeToolRequests(requests, turn, deps) {
    const { runTool, ctx, query, toolResults, loopLog, loopSuffixRef } = deps;
    let suffix = loopSuffixRef.suffix || "";
    for (const req of requests) {
      const id = normalizeToolId(req.name);
      if (!deps.toolIds.has(id)) {
        suffix += "\nTool " + id + ": ERROR — tool not available.\n";
        loopLog.push({ turn, tool: id, ok: false, error: "unknown", auto: !!deps.auto });
        continue;
      }
      if (ctx.onToolProgress) ctx.onToolProgress({ phase: "start", tool: id, label: id });
      const res = await runTool(id, ctx, req.query || query);
      const key = id + "_L" + turn;
      toolResults[key] = res;
      loopLog.push({ turn, tool: id, ok: !(res && res.ok === false), auto: !!deps.auto });
      suffix +=
        "\n### Tool " +
        id +
        (deps.auto ? " (auto)" : "") +
        "\n" +
        (res && res.summary ? String(res.summary).slice(0, 2500) : "No data.") +
        "\n";
      if (ctx.onToolProgress) ctx.onToolProgress({ phase: "done", tool: id, ok: !(res && res.ok === false) });
    }
    loopSuffixRef.suffix = suffix;
    return suffix;
  }

  async function runModelWithLoop(deps) {
    const {
      enhanceModelCall,
      runTool,
      ctx,
      route,
      query,
      plan,
      initialToolResults,
      onToken,
      toolIds,
      maxTurnsOverride,
    } = deps;

    const maxTurns =
      typeof maxTurnsOverride === "number" && maxTurnsOverride > 0
        ? Math.min(MAX_LOOP_TURNS, maxTurnsOverride)
        : MAX_LOOP_TURNS;

    if (!shouldUseAgentLoop(query, route, plan, (ctx.halModels && ctx.halModels.config && ctx.halModels.config.agentProgramming) || {})) {
      const single = await enhanceModelCall(ctx, route, query, plan, initialToolResults || {}, onToken);
      return Object.assign({}, single, { toolResults: initialToolResults || {}, loopTurns: 0, loopLog: [] });
    }

    const agentCfg = (ctx.halModels && ctx.halModels.config && ctx.halModels.config.agentProgramming) || {};
    let toolResults = Object.assign({}, initialToolResults || {});
    let loopSuffix = "";
    const loopLog = [];
    let lastResult = null;
    let autoFallbackDone = false;
    const activePlan = Object.assign({}, plan, { agentToolLoop: true });
    const loopSuffixRef = { suffix: loopSuffix };

    if (agentCfg.agentAutoTools !== false && Object.keys(toolResults).length < 2) {
      const prefetch = suggestAutoTools(query, activePlan, toolResults, toolIds, agentCfg).slice(0, 2);
      if (prefetch.length) {
        if (ctx.onToolProgress) ctx.onToolProgress({ phase: "loop", tool: "agent-loop", label: "Auto prefetch" });
        await executeToolRequests(prefetch, -1, {
          runTool,
          ctx,
          query,
          toolResults,
          loopLog,
          loopSuffixRef,
          toolIds,
          auto: true,
        });
        loopSuffix = loopSuffixRef.suffix;
      }
    }

    for (let turn = 0; turn < maxTurns; turn++) {
      activePlan.loopSuffix = loopSuffix;
      if (ctx.onToolProgress && turn > 0) {
        ctx.onToolProgress({ phase: "loop", tool: "agent-loop", label: "Agent loop turn " + (turn + 1) });
      }
      const result = await enhanceModelCall(
        ctx,
        route,
        query,
        activePlan,
        toolResults,
        turn === 0 ? onToken : undefined,
      );
      if (!result || !result.text) break;
      lastResult = result;

      let requests = parseToolRequests(result.text);
      if (!requests.length && result.toolCalls && result.toolCalls.length) {
        requests = parseCloudToolCalls(result.toolCalls);
      }
      if (!requests.length) {
        if (
          turn === 0 &&
          !autoFallbackDone &&
          agentCfg.agentAutoTools !== false &&
          suggestAutoTools(query, activePlan, toolResults, toolIds, agentCfg).length
        ) {
          autoFallbackDone = true;
          const auto = suggestAutoTools(query, activePlan, toolResults, toolIds, agentCfg);
          if (auto.length) {
            loopSuffix += "\n(Model did not request tools — running auto gather.)\n";
            loopSuffixRef.suffix = loopSuffix;
            await executeToolRequests(auto, turn, {
              runTool,
              ctx,
              query,
              toolResults,
              loopLog,
              loopSuffixRef,
              toolIds,
              auto: true,
            });
            loopSuffix = loopSuffixRef.suffix;
            continue;
          }
        }
        return {
          text: stripToolBlocks(result.text),
          lane: result.lane,
          toolResults,
          loopTurns: turn + 1,
          loopLog,
        };
      }

      loopSuffixRef.suffix = loopSuffix;
      await executeToolRequests(requests, turn, {
        runTool,
        ctx,
        query,
        toolResults,
        loopLog,
        loopSuffixRef,
        toolIds,
        auto: false,
      });
      loopSuffix = loopSuffixRef.suffix;
    }

    return {
      text: stripToolBlocks((lastResult && lastResult.text) || "") || "Agent loop reached the turn limit. Try a narrower question.",
      lane: (lastResult && lastResult.lane) || route.lane || "chat8b",
      toolResults,
      loopTurns: maxTurns,
      loopLog,
    };
  }

  async function applyPatchesFromText(text, ctx, toolResults, runTool) {
    const patches = parseAllPatches(text);
    if (!patches.length) return [];
    const bridge =
      typeof DesktopBridge !== "undefined"
        ? DesktopBridge
        : typeof global !== "undefined" && global.DesktopBridge
          ? global.DesktopBridge
          : null;
    if (bridge && typeof bridge.applyProgramPatches === "function") {
      const payload = await bridge.applyProgramPatches(patches, false);
      toolResults.apply_program_patches = {
        ok: !!(payload && payload.ok),
        summary: payload && payload.text ? payload.text : "Patch batch finished.",
      };
      return payload && payload.results ? payload.results : [];
    }
    const applied = [];
    for (const spec of patches) {
      ctx.pendingPatch = spec;
      const res = await runTool("apply_program_patch", ctx, "");
      toolResults["apply_" + spec.file] = res;
      applied.push(res);
    }
    return applied;
  }

  async function runValidateRetryLoop(deps) {
    const { ctx, query, outcome, toolResults, route, activePlan, onToken, runModelWithLoopFn, shouldValidate, planOnly } = deps;
    if (!outcome || !outcome.text || planOnly) return outcome;

    let text = outcome.text;
    let lane = outcome.lane;

    const patches = parseAllPatches(text);
    const autoPatch = (ctx.halModels && ctx.halModels.config && ctx.halModels.config.agentProgramming) || {};
    if (patches.length && autoPatch.autoApplyPatches !== false) {
      await applyPatchesFromText(text, ctx, toolResults, deps.runTool);
    }

    const needsVal =
      shouldValidate ||
      (patches.length && autoPatch.autoApplyPatches !== false) ||
      /\bvalidate|validation|make.*pass\b/i.test(query);
    if (!needsVal) return outcome;

    for (let attempt = 0; attempt <= MAX_VALIDATE_RETRIES; attempt++) {
      const val = await deps.runTool("run_hal_validation", ctx, query);
      toolResults.run_hal_validation = val;
      if (val && val.ok) {
        outcome.text = text.replace(/\s+$/, "") + "\n\nValidation passed (validate-hal.mjs" + (attempt ? ", retry " + attempt : "") + ").";
        outcome.lane = lane;
        return outcome;
      }
      if (attempt >= MAX_VALIDATE_RETRIES) {
        outcome.text =
          text.replace(/\s+$/, "") +
          "\n\nValidation failed after " +
          (MAX_VALIDATE_RETRIES + 1) +
          " attempt(s):\n" +
          String((val && val.summary) || "").slice(0, 1600);
        return outcome;
      }
      const fixQuery =
        query +
        "\n\nvalidate-hal.mjs failed. Fix the program and output corrected <<<patch blocks if needed.\n" +
        String((val && val.summary) || "").slice(0, 2200);
      const fixPlan = Object.assign({}, activePlan, {
        agentToolLoop: true,
        loopSuffix: "\nValidation errors:\n" + String((val && val.summary) || "").slice(0, 2200),
      });
      const retry = await runModelWithLoopFn({
        enhanceModelCall: deps.enhanceModelCall,
        runTool: deps.runTool,
        ctx,
        route: deps.escalateRoute(route, fixQuery),
        query: fixQuery,
        plan: fixPlan,
        initialToolResults: toolResults,
        onToken,
        toolIds: deps.toolIds,
      });
      if (retry && retry.text) {
        text = retry.text;
        lane = retry.lane || lane;
        Object.assign(toolResults, retry.toolResults || {});
        await applyPatchesFromText(text, ctx, toolResults, deps.runTool);
      }
    }
    outcome.text = text;
    outcome.lane = lane;
    return outcome;
  }

  function isPlanOnlyQuery(query) {
    return /\b(plan first|plan only|approve before|proposal only|do not apply|dry run)\b/i.test(String(query || ""));
  }

  global.HalAgentLoop = {
    VERSION,
    TOOL_LOOP_GUIDE,
    get MAX_LOOP_TURNS() {
      return MAX_LOOP_TURNS;
    },
    get MAX_TOOLS_PER_TURN() {
      return MAX_TOOLS_PER_TURN;
    },
    configureFromAgentProgramming,
    parseCloudToolCalls,
    parseToolRequests,
    parseAllPatches,
    stripToolBlocks,
    shouldUseAgentLoop,
    suggestAutoTools,
    runModelWithLoop,
    applyPatchesFromText,
    runValidateRetryLoop,
    isPlanOnlyQuery,
  };
})(typeof globalThis !== "undefined" ? globalThis : typeof window !== "undefined" ? window : this);
