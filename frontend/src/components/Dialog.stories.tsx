import type { Meta, StoryObj } from "@storybook/react";
import type React from "react";
import { useState } from "react";
import "./Dialog.stories.css";

const Dialog = ({ open, onClose, children }: { open: boolean; onClose: () => void; children: React.ReactNode }) =>
  open ? (
    <div className="dialog-story__overlay">
      <div className="dialog-story__panel">
        {children}
        <div className="dialog-story__actions">
          <button type="button" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  ) : null;

const meta: Meta<typeof Dialog> = {
  title: "Components/Dialog",
  component: Dialog,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof Dialog>;

export const Open: Story = {
  render: () => {
    const [open, setOpen] = useState(true);
    return (
      <Dialog open={open} onClose={() => setOpen(false)}>
        Dialog content goes here.
      </Dialog>
    );
  },
};
