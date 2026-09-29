import ResourcePage from "../components/ResourcePage"
import { locationsApi } from "../api/resources"

const columns = [
    { key: "name", header: "Name" },
    {
        key: "position",
        header: "Warehouse › Aisle › Shelf › Bin",
        render: (r) => [r.warehouse, r.aisle, r.shelf, r.bin].filter(Boolean).join(" › ") || "—",
    },
    { key: "description", header: "Description" },
]
const fields = [
    { name: "name", label: "Name", required: true, maxLength: 150 },
    { name: "description", label: "Description", type: "textarea" },
    { name: "warehouse", label: "Warehouse", maxLength: 100, half: true },
    { name: "aisle", label: "Aisle", maxLength: 50, half: true },
    { name: "shelf", label: "Shelf", maxLength: 50, half: true },
    { name: "bin", label: "Bin", maxLength: 50, half: true },
]
const filters = [
    { key: "warehouse", label: "All warehouses", loadOptions: () => locationsApi.warehouses() },
    {
        key: "has_products",
        label: "All locations",
        options: [
            { value: "true", label: "In use" },
            { value: "false", label: "Empty" },
        ],
    },
]

export default function LocationsPage() {
    return (
        <ResourcePage
            title="Locations"
            subtitle="Warehouses, aisles, shelves, and bins."
            singular="location"
            plural="locations"
            api={locationsApi}
            columns={columns}
            fields={fields}
            filters={filters}
            searchPlaceholder="Search locations…"
        />
    )
}