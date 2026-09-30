import { useEffect } from "react"
import "./styles/Resource.css"

export default function Modal({ title, onClose, footer, wide = false, children }) {
    useEffect(() => {
        function onKey(e) {
            if (e.key === "Escape") onClose()
        }
        document.addEventListener("keydown", onKey)
        return () => document.removeEventListener("keydown", onKey)
    }, [onClose])

    return (
        <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
            <div className={`modal${wide ? " modal--wide" : ""}`} role="dialog" aria-modal="true" aria-label={title}>
                <header className="modal-head">
                    <h2>{title}</h2>
                    <button className="modal-close" onClick={onClose} aria-label="Close">×</button>
                </header>
                <div className="modal-body">{children}</div>
                {footer && <footer className="modal-foot">{footer}</footer>}
            </div>
        </div>
    )
}

export function ConfirmDialog({ title, children, confirmLabel = "Delete", busy, error, onConfirm, onCancel }) {
    return (
        <Modal
            title={title}
            onClose={busy ? () => {} : onCancel}
            footer={
                <>
                    <button className="btn btn-ghost" onClick={onCancel} disabled={busy}>Cancel</button>
                    <button className="btn btn-danger-solid" onClick={onConfirm} disabled={busy}>
                        {busy ? "Working…" : confirmLabel}
                    </button>
                </>
            }
        >
            {error && <div className="form-error" style={{ marginBottom: 12 }}>{error}</div>}
            <p>{children}</p>
        </Modal>
    )
}