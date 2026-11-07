import { Link, NavLink } from 'react-router-dom'
import { useLibrary } from '../context/useLibrary.js'

export function Logo() {
  return (
    <Link to="/" className="logo" aria-label="OAuth Guides home">
      {/* The journey strip in miniature: agent, you, then the wait. Same mark as the favicon. */}
      <svg width="30" height="30" viewBox="0 0 64 64" aria-hidden="true">
        <defs>
          <pattern id="logo-wait" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="7" height="7" fill="#303030" />
            <rect width="3.5" height="7" fill="#4a4a4a" />
          </pattern>
        </defs>
        <rect width="64" height="64" rx="15" fill="#111" />
        <rect x="1.5" y="1.5" width="61" height="61" rx="13.5" fill="none" stroke="#444" strokeWidth="3" />
        <rect x="8" y="16" width="12" height="32" rx="5" fill="#e9b3ff" />
        <rect x="23" y="16" width="12" height="32" rx="5" fill="#4d5dff" />
        <rect x="38" y="16" width="18" height="32" rx="5" fill="url(#logo-wait)" stroke="#8a8a8a" strokeWidth="2" />
      </svg>
      <span>OAuth Guides</span>
    </Link>
  )
}

export function Nav() {
  const { guides } = useLibrary()
  return (
    <header className="nav">
      <div className="page nav-inner">
        <Logo />
        <nav className="nav-links" aria-label="Main">
          <NavLink to="/" end>
            Library{guides.length ? <span className="nav-count">{guides.length}</span> : null}
          </NavLink>
          <NavLink to="/compare">Compare</NavLink>
        </nav>
        <Link to="/#search" className="btn nav-cta">
          Research an app
        </Link>
      </div>
    </header>
  )
}

export function Footer() {
  return (
    <footer className="footer">
      <div className="page footer-inner">
        <p className="muted">
          Guides are researched by an AI agent from public sources, and every quote is checked against the page it came from.
          Check the provider’s current docs before you submit anything.
        </p>
        <p className="label">An independent take-home project, not affiliated with any provider.</p>
      </div>
    </footer>
  )
}

export function ServerNotice({ phase, error, onRetry }) {
  if (phase === 'ready') return null
  if (phase === 'error') {
    return (
      <div className="notice notice-bad" role="alert">
        <span>{error || 'Could not reach the server.'}</span>
        <button className="btn" onClick={onRetry}>
          Retry
        </button>
      </div>
    )
  }
  return (
    <div className="notice" role="status">
      <span className="spinner" aria-hidden="true" />
      {phase === 'waking' ? 'Waking the server. The first visit can take a few seconds…' : 'Loading the library…'}
    </div>
  )
}
