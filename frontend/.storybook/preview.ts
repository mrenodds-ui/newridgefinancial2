import type { Preview } from "@storybook/react";

const preview: Preview = {
  parameters: {
    layout: "padded",

    backgrounds: {
      default: "light",
      values: [
        { name: "light", value: "#f6f4f0" },
        { name: "dark", value: "#0f2233" },
      ],
    },

    a11y: {
      // 'todo' - show a11y violations in the test UI only
      // 'error' - fail CI on a11y violations
      // 'off' - skip a11y checks entirely
      test: "todo"
    }
  },
};

export default preview;
