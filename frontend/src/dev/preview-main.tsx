import { createRoot } from 'react-dom/client'
import { Preview } from './Preview'
import '../tailwind.css'

const el = document.getElementById('root')
if (!el) throw new Error('Missing #root')
createRoot(el).render(<Preview />)
