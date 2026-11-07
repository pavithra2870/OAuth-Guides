import { Link } from 'react-router-dom'
import { useDocumentTitle } from '../hooks/hooks.js'

export default function NotFound() {
  useDocumentTitle('Page not found')
  return (
    <main className="page narrow">
      <div className="card empty">
        <span className="label">404</span>
        <h1>That page doesn’t exist</h1>
        <p className="muted">The link may be mistyped, or the guide was never created.</p>
        <Link className="btn btn-solid" to="/">
          Back to the library
        </Link>
      </div>
    </main>
  )
}
