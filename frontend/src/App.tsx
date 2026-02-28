import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import Discover from './pages/Discover'
import Queue from './pages/Queue'
import History from './pages/History'
import Knowledge from './pages/Knowledge'
import Settings from './pages/Settings'

export default function App() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 ml-16 p-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/discover" element={<Discover />} />
          <Route path="/queue" element={<Queue />} />
          <Route path="/history" element={<History />} />
          <Route path="/knowledge" element={<Knowledge />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  )
}
