/** MSW browser worker（dev:mock 模式：`npm run dev:mock`） */
import { setupWorker } from 'msw/browser'
import { handlers } from './handlers'

export const worker = setupWorker(...handlers)
