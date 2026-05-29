import { pgTable, serial, text, real, timestamp, boolean, integer, jsonb } from "drizzle-orm/pg-core";

export const analyses = pgTable("analyses", {
  id: serial("id").primaryKey(),
  ticker: text("ticker").notNull(),
  companyName: text("company_name").notNull(),
  period: text("period").notNull(),
  url: text("url").notNull(),
  veracityScore: real("veracity_score").notNull(),
  cost: real("cost").notNull(),
  reportJson: jsonb("report_json").notNull(), // The complete AnalystSummary model
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export const veracityLogs = pgTable("veracity_logs", {
  id: serial("id").primaryKey(),
  analysisId: integer("analysis_id").references(() => analyses.id, { onDelete: "cascade" }),
  metricName: text("metric_name").notNull(),
  extractedValue: text("extracted_value").notNull(),
  sourceTable: text("source_table"),
  sourceRow: text("source_row"),
  isVerified: boolean("is_verified").notNull(),
});
