import { toast } from "sonner";

export const showError = (msg: string) => toast.error(msg);
export const showSuccess = (msg: string) => toast.success(msg);
