import type { Meta, StoryObj } from "@storybook/react";
import { DashboardCard } from "./DashboardCard";

const meta: Meta<typeof DashboardCard> = {
  title: "Components/DashboardCard",
  component: DashboardCard,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof DashboardCard>;

export const Default: Story = {
  args: {
    title: "Card Title",
    accent: "gold",
    children: "This is a dashboard card.",
  },
};
