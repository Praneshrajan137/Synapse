import type { Meta, StoryObj } from "@storybook/react";
import { Button } from "./Button";
import {
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "./Dialog";

const meta = {
  title: "Primitives/Dialog",
  component: Dialog,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Dialog>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  render: () => (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="signal">Confirm override</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Confirm override</DialogTitle>
          <DialogDescription>
            This approves decision 4f2a-91 on behalf of the operator. The action is
            audit-logged and immutable.
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          <p style={{ color: "var(--color-ink-secondary)", fontSize: 14 }}>
            Confidence was 0.42 — below the Tier 3 escalation threshold.
          </p>
        </DialogBody>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="ghost">Cancel</Button>
          </DialogClose>
          <DialogClose asChild>
            <Button variant="signal">Approve</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  ),
};
