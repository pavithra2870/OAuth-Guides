import { useEffect } from 'react'
import { Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { Footer, Nav } from './components/Chrome.jsx'
import Compare from './pages/Compare.jsx'
import Guide from './pages/Guide.jsx'
import Home from './pages/Home.jsx'
import NotFound from './pages/NotFound.jsx'
import Research from './pages/Research.jsx'

function Layout() {
  const { pathname, hash } = useLocation()
  // New page = start at the top (unless the link targets a section on the page).
  useEffect(() => {
    if (!hash) window.scrollTo(0, 0)
  }, [pathname, hash])

  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <Nav />
      <div id="main">
        <Outlet />
      </div>
      <Footer />
    </>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="g/:slug" element={<Guide />} />
        <Route path="research" element={<Research />} />
        <Route path="compare" element={<Compare />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
