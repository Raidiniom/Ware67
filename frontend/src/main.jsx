import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import { AuthProvider } from './context/AuthContext.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import LoginPage from './pages/LoginPage.jsx'
import RegisterPage from './pages/RegisterPage.jsx'
import ForgotPasswordPage from './pages/ForgotPasswordPage.jsx'
import LandingPage from './pages/LandingPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import ProductsPage from './pages/ProductsPage.jsx'
import UsersPage from './pages/UsersPage.jsx'
import CategoriesPage from './pages/CategoriesPage.jsx'
import SuppliersPage from './pages/SuppliersPage.jsx'
import LocationsPage from './pages/LocationsPage.jsx'
import TransactionsPage from './pages/TransactionsPage.jsx'
import AdjustmentsPage from './pages/AdjustmentsPage.jsx'
import AuditLogsPage from './pages/AuditLogsPage.jsx'
import './readability.css'

const protect = (page) => <ProtectedRoute>{page}</ProtectedRoute>

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/" element={<LandingPage />} />
          <Route path="/dashboard" element={protect(<DashboardPage />)} />
          <Route path="/products" element={protect(<ProductsPage />)} />
          <Route path="/users" element={protect(<UsersPage />)} />
          <Route path="/categories" element={protect(<CategoriesPage />)} />
          <Route path="/suppliers" element={protect(<SuppliersPage />)} />
          <Route path="/locations" element={protect(<LocationsPage />)} />
          <Route path="/transactions" element={protect(<TransactionsPage />)} />
          <Route path="/adjustments" element={protect(<AdjustmentsPage />)} />
          <Route path="/audit-logs" element={protect(<AuditLogsPage />)} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)