import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ActivityLogsPage } from './pages/ActivityLogsPage'
import { DashboardPage } from './pages/DashboardPage'
import { WorkItemDetailPage } from './pages/WorkItemDetailPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="logs" element={<ActivityLogsPage />} />
          <Route path="logs/:workId" element={<WorkItemDetailPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
