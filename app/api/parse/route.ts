import { NextResponse } from "next/server";

// TODO(api): validate the request body with Zod and call parseProblem().
export async function POST() {
  return NextResponse.json({ error: "Not Implemented" }, { status: 501 });
}
