import type { Meta, StoryObj } from "@storybook/react";

import { OfflineBanner } from "../components/OfflineBanner";

const meta: Meta<typeof OfflineBanner> = {
  title: "Components/OfflineBanner",
  component: OfflineBanner,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof OfflineBanner>;

/**
 * NOTE: OfflineBanner reads navigator.onLine at render time.
 * In Storybook it will be hidden (browser reports online).
 * To preview, temporarily override navigator.onLine in the story
 * or view the component source directly.
 */
export const Default: Story = {};
