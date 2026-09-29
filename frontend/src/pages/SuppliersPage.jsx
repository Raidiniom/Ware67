import ResourcePage from "../components/ResourcePage"
import { suppliersApi } from "../api/resources"

const columns = [
    { key: "name", header: "Name" },
    { key: "contact_person", header: "Contact" },
    { key: "contact_number", header: "Phone" },
    { key: "email", header: "Email" },
]
const fields = [
    { name: "name", label: "Name", required: true, maxLength: 150 },
    { name: "contact_person", label: "Contact person", maxLength: 150, half: true },
    { name: "contact_number", label: "Contact number", maxLength: 50, half: true },
    { name: "email", label: "Email", type: "email", maxLength: 150 },
    { name: "address", label: "Address", type: "textarea" },
]
const filters = [
    {
        key: "has_products",
        label: "All suppliers",
        options: [
            { value: "true", label: "With products" },
            { value: "false", label: "No products" },
        ],
    },
    {
        key: "has_email",
        label: "Any email status",
        options: [
            { value: "true", label: "Has email" },
            { value: "false", label: "No email" },
        ],
    },
]

export default function SuppliersPage() {
    return (
        <ResourcePage
            title="Suppliers"
            subtitle="Vendor contacts and details."
            singular="supplier"
            plural="suppliers"
            api={suppliersApi}
            columns={columns}
            fields={fields}
            filters={filters}
            searchPlaceholder="Search name, contact, email…"
        />
    )
}