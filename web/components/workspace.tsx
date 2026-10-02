"use client";

import {
  ChangeEvent,
  DragEvent,
  FormEvent,
  KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { getSupabaseClient } from "@/lib/supabase/client";

type Citation = {
  chunk_id: number;
  supporting_quote: string;
  pages: number[];
  headings: string[];
};

type GroundedAnswer = {
  answer: string;
  citations: Citation[];
  insufficient_evidence: boolean;
};

type RetrievedChunk = {
  chunk_id: number;
  text: string;
  score: number;
  headings: string[];
  pages: number[];
  added_via: string[];
};

type ContractQuestionResponse = {
  query: string;
  embedding_model: string;
  answer_model: string;
  retrieval_mode: "chunks" | "graph";
  answer: GroundedAnswer;
  retrieved_chunks: RetrievedChunk[];
  graph_added_chunk_ids: number[];
};

type ModelChoice = "local_qwen" | "groq_qwen";

type ChatTurn = {
  question: string;
  result: ContractQuestionResponse;
};

const suggestions = [
  "What is the liability cap for indemnification breaches?",
  "When can either party terminate the agreement?",
  "What restrictions apply to the customer?",
];

function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const paths: Record<string, React.ReactNode> = {
    upload: <><path d="M12 16V4m0 0L7 9m5-5 5 5" /><path d="M20 16.5v2A1.5 1.5 0 0 1 18.5 20h-13A1.5 1.5 0 0 1 4 18.5v-2" /></>,
    file: <><path d="M13 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10z" /><path d="M13 3v7h7M8 14h8m-8 4h8" /></>,
    send: <><path d="m21 3-7.2 18-3.9-7.9L2 9.2 21 3Z" /><path d="M10 13 21 3" /></>,
    chevron: <path d="m9 18 6-6-6-6" />,
    logout: <><path d="M10 17l5-5-5-5" /><path d="M15 12H3" /><path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6" /></>,
    quote: <><path d="M10 11H5a2 2 0 0 0-2 2v5h7v-7Zm11 0h-5a2 2 0 0 0-2 2v5h7v-7Z" /><path d="M10 11c0-3 1-5 3-6m8 6c0-3 1-5 3-6" /></>,
    sparkle: <><path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3Z" /><path d="m19 16 .8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8L19 16Z" /></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] ?? paths.file}</svg>;
}

function BrandMark() {
  return <div className="brand-lockup workspace-brand"><span className="brand-mark" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none"><path d="M8 4.75h10l6 6v16.5H8V4.75Z" /><path d="M18 4.75v6h6M12 16h8M12 20h8" /><circle cx="9" cy="23" r="3.25" /><path d="m7.8 23 1 1 2-2" /></svg></span><span>LexGraph</span></div>;
}

export function Workspace() {
  const router = useRouter();
  const [authReady, setAuthReady] = useState(false);
  const [userEmail, setUserEmail] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [fileUrl, setFileUrl] = useState("");
  const fileUrlRef = useRef("");
  const [pageNumber, setPageNumber] = useState(1);
  const [dragging, setDragging] = useState(false);
  const [question, setQuestion] = useState("");
  const [useRelationshipGraph, setUseRelationshipGraph] = useState(false);
  const [semanticModel, setSemanticModel] = useState<ModelChoice>("local_qwen");
  const [answerModel, setAnswerModel] = useState<ModelChoice>("local_qwen");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [loadingStage, setLoadingStage] = useState(0);
  const fileInput = useRef<HTMLInputElement>(null);
  const chatScroll = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const supabase = getSupabaseClient();
    if (!supabase) {
      router.replace("/");
      return;
    }

    let mounted = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!mounted) return;
      if (!data.session) router.replace("/");
      else setUserEmail(data.session.user.email ?? "");
      setAuthReady(true);
    });
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session) router.replace("/");
      else setUserEmail(session.user.email ?? "");
    });
    return () => {
      mounted = false;
      data.subscription.unsubscribe();
    };
  }, [router]);

  useEffect(() => () => {
    if (fileUrlRef.current) URL.revokeObjectURL(fileUrlRef.current);
  }, []);

  useEffect(() => {
    const container = chatScroll.current;
    if (container) {
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    }
  }, [turns, busy]);

  useEffect(() => {
    if (!busy) return;
    const timer = window.setInterval(() => setLoadingStage((stage) => (stage + 1) % 3), 7000);
    return () => window.clearInterval(timer);
  }, [busy]);

  function selectFile(candidate: File | undefined) {
    if (!candidate) return;
    if (candidate.type !== "application/pdf" && !candidate.name.toLowerCase().endsWith(".pdf")) {
      setError("Please choose a PDF file.");
      return;
    }
    setError("");
    if (fileUrlRef.current) URL.revokeObjectURL(fileUrlRef.current);
    fileUrlRef.current = URL.createObjectURL(candidate);
    setFileUrl(fileUrlRef.current);
    setFile(candidate);
    setPageNumber(1);
    setTurns([]);
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    selectFile(event.target.files?.[0]);
    event.target.value = "";
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    selectFile(event.dataTransfer.files?.[0]);
  }

  async function submitQuestion(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    const currentQuestion = question.trim();
    if (!file || !currentQuestion || busy) return;
    setError("");
    setLoadingStage(0);
    setBusy(true);
    setQuestion("");

    try {
      const formData = new FormData();
      formData.append("file", file, file.name);
      formData.append("query", currentQuestion);
      formData.append("top_k", "5");
      formData.append("use_relationship_graph", String(useRelationshipGraph));
      formData.append("semantic_model", semanticModel);
      formData.append("answer_model", answerModel);
      const response = await fetch("/api/ask-contract", { method: "POST", body: formData });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "The contract question could not be processed.");
      const result = payload as ContractQuestionResponse;
      setTurns((previous) => [...previous, { question: currentQuestion, result }]);
    } catch (requestError) {
      setQuestion(currentQuestion);
      setError(requestError instanceof Error ? requestError.message : "Something went wrong while contacting the API.");
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    await getSupabaseClient()?.auth.signOut();
    router.replace("/");
  }

  function removeFile() {
    if (fileUrlRef.current) URL.revokeObjectURL(fileUrlRef.current);
    fileUrlRef.current = "";
    setFileUrl("");
    setFile(null);
    setTurns([]);
  }

  function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitQuestion();
    }
  }

  if (!authReady) {
    return <main className="workspace-loading"><span className="loading-orb" /> Opening your workspace…</main>;
  }

  return (
    <main className="workspace-shell">
      <header className="topbar">
        <div className="topbar-left"><BrandMark /><span className="topbar-divider" /><span className="topbar-context">Contract workspace</span></div>
        <div className="topbar-right">
          <div className="topbar-status"><span /> LOCAL WORKSPACE</div>
          <div className="user-pill"><span className="user-avatar">{userEmail.slice(0, 1).toUpperCase() || "U"}</span><span className="user-email">{userEmail}</span></div>
          <button className="icon-button signout-button" onClick={signOut} aria-label="Sign out" title="Sign out"><Icon name="logout" /></button>
        </div>
      </header>

      <section className="workspace-main">
        <div className="workspace-intro">
          <div><div className="eyebrow"><span className="eyebrow-dot" /> EVIDENCE WORKSPACE</div><h1>Ask your contract.</h1><p>Upload an agreement, ask a question, and follow the evidence back to the page.</p></div>
          <div className="intro-step"><span>01</span><span className="step-line" /><span>02</span><span className="step-label">DOCUMENT <i /> QUESTION</span></div>
        </div>

        <div className="workbench">
          <section className="document-pane" aria-label="Contract document viewer">
            {!file ? (
              <>
                <div className="pane-header document-header">
                  <div className="pane-title"><span className="pane-icon"><Icon name="file" /></span><div><strong>Contract document</strong><span>Upload a PDF to begin</span></div></div>
                </div>
                <div className={`upload-stage ${dragging ? "is-dragging" : ""}`} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
                  <input className="visually-hidden" type="file" accept="application/pdf,.pdf" onChange={onFileChange} />
                  <div className="upload-illustration"><div className="upload-page-back" /><div className="upload-page"><Icon name="file" size={28} /><span /><span /><span /></div><span className="upload-plus">+</span></div>
                  <h2>Bring an agreement into focus</h2>
                  <p>Drop a PDF here or browse your files. Your document stays in this session.</p>
                  <button className="primary-button choose-file" onClick={() => fileInput.current?.click()}><Icon name="upload" size={16} /> Choose a PDF</button>
                  <span className="file-hint">PDF DOCUMENTS <i /> PROCESSED LOCALLY</span>
                </div>
              </>
            ) : (
              <>
                <div className="pdf-viewer-wrap">
                  <div className="pdf-viewer-toolbar"><span><i className="viewer-dot" /> DOCUMENT PREVIEW</span><span className="pdf-toolbar-actions">PAGE <strong>{pageNumber}</strong><button className="viewer-clear" onClick={removeFile} aria-label="Remove PDF" title="Remove PDF">×</button></span></div>
                  <iframe key={`${fileUrl}-${pageNumber}`} className="pdf-viewer" title={`Preview of ${file.name}`} src={`${fileUrl}#page=${pageNumber}&view=Fit`} />
                </div>
              </>
            )}
            <input ref={fileInput} className="visually-hidden" type="file" accept="application/pdf,.pdf" onChange={onFileChange} />
            {!file && <div className="document-footer"><span><span className="footer-live-dot" /> PRIVATE SESSION</span><span>PDF VIEWER <i /> EVIDENCE LINKED</span></div>}
          </section>

          <section className="chat-pane" aria-label="Contract question and answers">
            <div className="pane-header chat-header"><div className="pane-title"><span className="pane-icon chat-pane-icon"><Icon name="sparkle" /></span><div><strong>Ask LexGraph</strong><span>Answers grounded in your agreement</span></div></div></div>
            <div className="retrieval-mode">
              <button
                className={`mode-switch ${useRelationshipGraph ? "mode-switch-on" : ""}`}
                type="button"
                role="switch"
                aria-checked={useRelationshipGraph}
                aria-label="Enhanced retrieval"
                disabled={busy}
                onClick={() => setUseRelationshipGraph((enabled) => !enabled)}
              ><span /></button>
            </div>
            <div className="model-selectors">
              <label><span>Semantic extraction</span><select value={semanticModel} onChange={(event) => setSemanticModel(event.target.value as ModelChoice)} disabled={busy}><option value="local_qwen">Local Qwen 2.5 · 3B</option><option value="groq_qwen">Groq Qwen 3.8 · 27B</option></select></label>
              <label><span>Answer generation</span><select value={answerModel} onChange={(event) => setAnswerModel(event.target.value as ModelChoice)} disabled={busy}><option value="local_qwen">Local Qwen 2.5 · 3B</option><option value="groq_qwen">Groq Qwen 3.8 · 27B</option></select></label>
            </div>

            <div ref={chatScroll} className="chat-scroll">
              {turns.length === 0 && !busy ? (
                <div className="chat-empty">
                  <div className="chat-empty-mark"><Icon name="sparkle" size={22} /></div>
                  <span className="chat-empty-kicker">START WITH A QUESTION</span>
                  <h2>{file ? "What would you like to know?" : "Your contract, in context."}</h2>
                  <p>{file ? "Ask about a clause, obligation, deadline, or risk." : "Upload a PDF on the left, then ask a question about its terms."}</p>
                  <div className="suggestion-list">{suggestions.map((suggestion) => <button key={suggestion} className="suggestion-chip" disabled={!file} onClick={() => setQuestion(suggestion)}>{suggestion}<Icon name="chevron" size={14} /></button>)}</div>
                  <div className="chat-note"><span>↳</span> Every answer includes a quote and page reference.</div>
                </div>
              ) : (
                <div className="conversation-list">
                  {turns.map((turn, index) => {
                    const answer = turn.result.answer;
                    const chunks = turn.result.retrieved_chunks;
                    return <article className="conversation-turn" key={`${turn.question}-${index}`}>
                      <div className="user-question"><span className="question-avatar">{userEmail.slice(0, 1).toUpperCase() || "U"}</span><p>{turn.question}</p></div>
                      <div className="answer-block">
                        <div className="answer-byline"><span className="assistant-avatar"><Icon name="sparkle" size={15} /></span><strong>LexGraph</strong><span className="answer-model">{turn.result.answer_model ?? "Qwen"}</span></div>
                        <div className="answer-card">
                          {answer?.insufficient_evidence && <div className="evidence-warning">The retrieved passages may not fully answer this question.</div>}
                          <p className="answer-copy">{answer?.answer ?? "No answer was returned for this retrieval mode."}</p>
                          <div className="citation-heading"><span /> SUPPORTING EVIDENCE <span className="citation-count">{answer?.citations.length ?? 0}</span></div>
                          {answer?.citations.length ? <div className="citation-list">{answer.citations.map((citation, citationIndex) => <button className="citation-card" key={`${citation.chunk_id}-${citationIndex}`} onClick={() => setPageNumber(citation.pages[0] ?? 1)} title="Show cited page in the document viewer">
                            <span className="citation-topline"><span className="citation-section">{citation.headings[0] ?? `Chunk ${citation.chunk_id}`}</span><span className="citation-page">P. {citation.pages.join(", ") || "—"} <Icon name="chevron" size={13} /></span></span>
                            <span className="citation-quote">“{citation.supporting_quote}”</span>
                          </button>)}</div> : <p className="no-citations">No supporting passage was returned.</p>}
                          <details className="retrieved-details"><summary>Retrieved passages <span>{chunks.length}</span></summary><div className="retrieved-list">{chunks.map((chunk) => <div className="retrieved-item" key={chunk.chunk_id}><div><strong>{chunk.headings[0] ?? `Chunk ${chunk.chunk_id}`}</strong><span>Chunk {chunk.chunk_id} · p. {chunk.pages.join(", ") || "—"}{chunk.added_via.length > 0 ? ` · via ${chunk.added_via.join(", ")}` : ""}</span></div><p>{chunk.text.slice(0, 360)}{chunk.text.length > 360 ? "…" : ""}</p></div>)}</div></details>
                        </div>
                      </div>
                    </article>;
                  })}
                  {busy && <div className="thinking-row"><span className="thinking-indicator"><i /><i /><i /></span><div><strong>{useRelationshipGraph ? "Connecting contract provisions" : "Searching contract chunks"}</strong><span>{(useRelationshipGraph ? ["Reading agreement structure…", "Extracting linked provisions…", "Preparing cited answer…"] : ["Searching document chunks…", "Ranking relevant passages…", "Preparing cited answer…"])[loadingStage]}</span></div></div>}
                </div>
              )}
            </div>

            <div className="composer-area">
              {error && <div className="workspace-error" role="alert">{error}<button onClick={() => setError("")} aria-label="Dismiss error">×</button></div>}
              {!file && <div className="composer-file-prompt"><Icon name="file" size={15} /> Upload a contract to start asking questions.</div>}
              <form className="composer" onSubmit={submitQuestion}>
                <textarea value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={onComposerKeyDown} placeholder={file ? "Ask a question about this agreement…" : "Upload a PDF to enable questions"} disabled={!file || busy} rows={2} />
                <div className="composer-bottom"><span>Enter to send <i /> Shift + Enter for a new line</span><button className="send-button" type="submit" disabled={!file || !question.trim() || busy} aria-label="Send question">{busy ? <span className="send-spinner" /> : <Icon name="send" size={17} />}</button></div>
              </form>
              <div className="composer-disclaimer">AI answers can miss context. Check the cited contract language.</div>
            </div>
          </section>
        </div>
        <footer className="workspace-footer"><span>LEXGRAPH <i /> CONTRACT INTELLIGENCE</span><span>BUILT AROUND THE EVIDENCE</span></footer>
      </section>
    </main>
  );
}
