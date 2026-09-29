import ResourcePage from "../components/ResourcePage"
import { categoriesApi } from "../api/resources"

const columns = [
    { key: "name", header: "Name" },
    { key: "description", header: "Description" },
]
const fields = [
    { name: "name", label: "Name", required: true, maxLength: 150 },
    { name: "description", label: "Description", type: "textarea" },
]
const filters = [
    {
        key: "has_products",
        label: "All categories",
        options: [
            { value: "true", label: "With products" },
            { value: "false", label: "Empty" },
        ],
    },
]

export default function CategoriesPage() {
    return (
        <ResourcePage
            title="Categories"
            subtitle="Organize products into logical groups."
            singular="category"
            plural="categories"
            api={categoriesApi}
            columns={columns}
            fields={fields}
            filters={filters}
            searchPlaceholder="Search categories…"
        />
    )
}