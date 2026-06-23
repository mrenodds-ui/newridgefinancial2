const registry = require(''c:/New folder/scripts/halShellCommandRegistry.js'');
const prompt = "Using only safe aggregate dashboard values already available to HAL, give me an owner-ready monthly checkpoint with four labeled sections: 1) production trend and current level, 2) collections or AR risk, 3) expense or profitability uncertainty you cannot yet verify, and 4) the single safest next management action. Keep it concise and do not invent missing data.";
console.log(JSON.stringify(registry.resolveCommandIntent(prompt, {}), null, 2));
