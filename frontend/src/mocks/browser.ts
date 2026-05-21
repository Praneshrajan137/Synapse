import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

/** Browser MSW worker — started from main.tsx when mocking is enabled. */
export const worker = setupWorker(...handlers);
