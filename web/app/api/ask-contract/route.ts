export const runtime = "nodejs";

export async function POST(request: Request) {
  const apiUrl = process.env.CONTRACT_API_URL ?? "http://localhost:8000";

  try {
    const incoming = await request.formData();
    const file = incoming.get("file");
    const query = incoming.get("query");

    if (!(file instanceof File) || typeof query !== "string" || !query.trim()) {
      return Response.json(
        { detail: "A PDF file and a non-empty question are required." },
        { status: 400 },
      );
    }

    const outgoing = new FormData();
    outgoing.append("file", file, file.name);
    outgoing.append("query", query.trim());
    outgoing.append("top_k", String(incoming.get("top_k") ?? "5"));
    outgoing.append(
      "use_relationship_graph",
      incoming.get("use_relationship_graph") === "true" ? "true" : "false",
    );
    outgoing.append(
      "semantic_model",
      incoming.get("semantic_model") === "groq_qwen" ? "groq_qwen" : "local_qwen",
    );
    outgoing.append(
      "answer_model",
      incoming.get("answer_model") === "groq_qwen" ? "groq_qwen" : "local_qwen",
    );

    const upstream = await fetch(`${apiUrl.replace(/\/$/, "")}/ask-contract`, {
      method: "POST",
      body: outgoing,
      cache: "no-store",
    });
    const body = await upstream.text();

    return new Response(body, {
      status: upstream.status,
      headers: {
        "content-type": upstream.headers.get("content-type") ?? "application/json",
      },
    });
  } catch (error) {
    console.error("Contract question proxy failed", error);
    return Response.json(
      {
        detail:
          "Could not reach the contract API. Make sure the API is running and CONTRACT_API_URL is correct.",
      },
      { status: 502 },
    );
  }
}
