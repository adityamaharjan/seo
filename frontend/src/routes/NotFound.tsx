import { Link } from 'react-router-dom'

export function NotFound() {
  return (
    <div className="center-note">
      <h2>Page not found</h2>
      <p>
        <Link to="/app">Back to the page audit</Link>
      </p>
    </div>
  )
}
