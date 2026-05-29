"use server";

import { db } from "@/db";
import { analyses, veracityLogs } from "@/db/schema";
import { eq, desc } from "drizzle-orm";
import { revalidatePath } from "next/cache";

export async function saveAnalysisAction(data: {
  ticker: string;
  companyName: string;
  period: string;
  url: string;
  veracityScore: number;
  cost: number;
  reportJson: any;
  logs: Array<{
    metricName: string;
    extractedValue: string;
    sourceTable?: string;
    sourceRow?: string;
    isVerified: boolean;
  }>;
}) {
  try {
    // 1. Insert analysis header
    const [inserted] = await db.insert(analyses).values({
      ticker: data.ticker,
      companyName: data.companyName,
      period: data.period,
      url: data.url,
      veracityScore: data.veracityScore,
      cost: data.cost,
      reportJson: data.reportJson,
    }).returning();

    // 2. Insert veracity logs if present
    if (data.logs && data.logs.length > 0) {
      const logsToInsert = data.logs.map((log) => ({
        analysisId: inserted.id,
        metricName: log.metricName,
        extractedValue: log.extractedValue,
        sourceTable: log.sourceTable || null,
        sourceRow: log.sourceRow || null,
        isVerified: log.isVerified,
      }));
      await db.insert(veracityLogs).values(logsToInsert);
    }

    revalidatePath("/");
    return { success: true, id: inserted.id };
  } catch (error: any) {
    console.error("Error saving analysis to Neon:", error);
    return { success: false, error: error.message || "Failed to save to database." };
  }
}

export async function loadHistoryAction() {
  try {
    const list = await db.query.analyses.findMany({
      orderBy: [desc(analyses.createdAt)],
      limit: 15,
    });
    return { success: true, list };
  } catch (error: any) {
    console.error("Error loading history from Neon:", error);
    return { success: false, error: error.message || "Database is offline." };
  }
}

export async function deleteAnalysisAction(id: number) {
  try {
    await db.delete(analyses).where(eq(analyses.id, id));
    revalidatePath("/");
    return { success: true };
  } catch (error: any) {
    console.error("Error deleting analysis:", error);
    return { success: false, error: error.message };
  }
}
