import { PrismaClient } from '@prisma/client'
import { PrismaBetterSqlite3 } from '@prisma/adapter-better-sqlite3'
import path from 'path'

const dbUrl = process.env.DATABASE_URL || 'file:./dev.db'
// Strip the "file:" prefix for better-sqlite3
const dbPath = dbUrl.startsWith('file:') ? dbUrl.slice(5) : dbUrl

const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined
}

export const prisma =
  globalForPrisma.prisma ??
  new PrismaClient({
    adapter: new PrismaBetterSqlite3({ url: dbUrl }),
  })

if (process.env.NODE_ENV !== 'production') {
  globalForPrisma.prisma = prisma
}
