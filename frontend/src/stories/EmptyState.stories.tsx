import type { Meta, StoryObj } from "@storybook/react";

import { EmptyState } from "../components/EmptyState";

const meta: Meta<typeof EmptyState> = {
  title: "Components/EmptyState",
  component: EmptyState,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof EmptyState>;

export const Default: Story = {};

export const WithMessage: Story = {
  args: {
    title: "No KPI rows",
    message: "Run a refresh to pull data from SoftDent.",
  },
};

export const WithAction: Story = {
  args: {
    title: "No provider data",
    message: "No providers were found in the last refresh.",
    actionLabel: "Refresh now",
    onAction: () => alert("Refresh triggered"),
  },
};

export const NoResults: Story = {
  args: {
    title: "No results",
    message: "Try adjusting your filters.",
  },
};
