import { useState } from "react"
import { changePassword } from "../api/auth"
import { errorMessage } from "../api/resources"
import Modal from "./Modal"
import "./styles/Resource.css"
import "./styles/Ledger.css"

export default function ChangePasswordDialog({ onChanged, onCancel }) {
    const [current, setCurrent] = useState("")
    const [next, setNext] = useState("")
    const [confirm, setConfirm] = useState("")
    const [error, setError] = useState("")
    const [saving, setSaving] = useState(false)

    async function handleSubmit(e) {
        e.preventDefault()
        setError("")
        if (next !== confirm) {
            setError("The new passwords do not match.")
            return
        }
        setSaving(true)
        try {
            await changePassword(current, next)
            onChanged()
        } catch (err) {
            setError(errorMessage(err))
            setSaving(false)
        }
    }

    return (
        <Modal
            title="Change password"
            onClose={saving ? () => {} : onCancel}
            footer={
                <>
                    <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={saving}>
                        Cancel
                    </button>
                    <button type="submit" form="change-password-form" className="btn btn-primary" disabled={saving}>
                        {saving ? "Saving…" : "Change password"}
                    </button>
                </>
            }
        >
            <form id="change-password-form" className="record-form" onSubmit={handleSubmit}>
                {error && <div className="form-error">{error}</div>}

                <label className="field">
                    <span>Current password *</span>
                    <input
                        type="password"
                        value={current}
                        onChange={(e) => setCurrent(e.target.value)}
                        autoComplete="current-password"
                        required
                        autoFocus
                    />
                </label>
                <label className="field">
                    <span>New password *</span>
                    <input
                        type="password"
                        value={next}
                        onChange={(e) => setNext(e.target.value)}
                        autoComplete="new-password"
                        minLength={8}
                        maxLength={128}
                        required
                    />
                    <span className="field-hint">At least 8 characters.</span>
                </label>
                <label className="field">
                    <span>Repeat new password *</span>
                    <input
                        type="password"
                        value={confirm}
                        onChange={(e) => setConfirm(e.target.value)}
                        autoComplete="new-password"
                        required
                    />
                </label>
            </form>
        </Modal>
    )
}
