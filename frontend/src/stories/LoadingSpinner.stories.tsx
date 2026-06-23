import type { Meta, StoryObj } from "@storybook/react";

import { LoadingSpinner } from "../components/LoadingSpinner";

const meta: Meta<typeof LoadingSpinner> = {
  title: "Components/LoadingSpinner",
  component: LoadingSpinner,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof LoadingSpinner>;

export const Default: Story = {};

export const CustomLabel: Story = {
  args: { label: "Fetching KPI data…" },
};

export const AdminRefresh: Story = {
  args: { label: "Refreshing from SoftDent…" },
};
