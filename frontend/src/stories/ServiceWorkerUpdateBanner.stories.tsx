import type { Meta, StoryObj } from "@storybook/react";

import { ServiceWorkerUpdateBanner } from "../components/ServiceWorkerUpdateBanner";

const meta: Meta<typeof ServiceWorkerUpdateBanner> = {
  title: "Components/ServiceWorkerUpdateBanner",
  component: ServiceWorkerUpdateBanner,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof ServiceWorkerUpdateBanner>;

export const Visible: Story = {
  args: {
    onRefresh: () => alert("Refresh to update"),
  },
};
