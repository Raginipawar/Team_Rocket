import { useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";

/** 2.18 Confirm dialog: title, one line, primary + cancel. */
export function Dialog({ open, title, children, onClose, actions }: {
  open: boolean; title: string; children?: ReactNode; onClose: () => void; actions: ReactNode;
}) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="dlg-back" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
          <motion.div
            className="dlg" role="dialog" aria-modal="true" aria-label={title}
            initial={{ opacity: 0, y: 24, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 24 }}
            transition={{ duration: 0.22 }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3>{title}</h3>
            {children && <div className="dlg-body">{children}</div>}
            <div className="dlg-actions">{actions}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** 2.18 Reason picker: radio list, optional note, primary disabled until a reason is picked. */
export function ReasonDialog({ open, title, reasons, confirmLabel, danger, onClose, onConfirm }: {
  open: boolean; title: string; reasons: string[]; confirmLabel: string; danger?: boolean;
  onClose: () => void; onConfirm: (reason: string, note: string) => void;
}) {
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const close = () => { setReason(""); setNote(""); onClose(); };
  return (
    <Dialog
      open={open}
      title={title}
      onClose={close}
      actions={
        <>
          <button className="btn2 btn2-light" onClick={close}>Keep</button>
          <button
            className={`btn2 ${danger ? "btn2-danger" : "btn2-dark"}`}
            disabled={!reason}
            onClick={() => { onConfirm(reason, note); setReason(""); setNote(""); }}
          >
            {confirmLabel}
          </button>
        </>
      }
    >
      <div className="radio-list" role="radiogroup">
        {reasons.map((r) => (
          <label key={r} className={`radio${reason === r ? " on" : ""}`}>
            <input type="radio" name="reason" checked={reason === r} onChange={() => setReason(r)} />
            <span className="radio-dot" />{r}
          </label>
        ))}
      </div>
      {reason && (
        <textarea className="field" rows={2} placeholder="Add a note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
      )}
    </Dialog>
  );
}
