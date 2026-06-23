import type { Meta, StoryObj } from "@storybook/react";
import { EmptyState } from "./EmptyState";

const meta: Meta<typeof EmptyState> = {
  title: "Components/EmptyState",
  component: EmptyState,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof EmptyState>;

export const Default: Story = {
  args: {
    title: "No data",
    message: "Nothing to show yet.",
  },
};

export const PermissionDenied: Story = {
  args: {
    title: "Permission Denied",
    message: "You do not have access to this resource.",
  },
};

export const Offline: Story = {
  args: {
    title: "Offline",
    message: "You are not connected to the internet.",
  },
};

export const Success: Story = {
  args: {
    title: "Success",
    message: "Your changes have been saved.",
  },
};
