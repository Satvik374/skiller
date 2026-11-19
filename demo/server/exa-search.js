/* Server-side Exa web search.
   This module lives outside src/ on purpose: exa-js needs the secret
   EXA_API_KEY, and anything imported by the Vite app is shipped to the
   browser. Agents can use it directly through `npm run search -- "query"`. */

import { pathToFileURL } from "node:url";
import Exa from "exa-js";

const MAX_RESULTS = 10;
let client;

function getClient() {
  const apiKey = process.env.EXA_API_KEY;
  if (!apiKey) {
    throw new Error(
      "EXA_API_KEY is not set. Export it in the environment or put it in " +
        "demo/.env.local (see demo/.env.example).",
    );
  }
  client ??= new Exa(apiKey);
  return client;
}

/**
 * Search the web with Exa and return the relevant pages plus query-focused
 * highlights. The API key stays in this process and never enters the result.
 */
export async function searchWeb(query, { numResults = 5 } = {}) {
  if (typeof query !== "string" || !query.trim()) {
    throw new Error("A non-empty search query is required.");
  }

  const limit = Math.min(Math.max(Math.trunc(numResults) || 5, 1), MAX_RESULTS);
  const response = await getClient().search(query.trim(), {
    type: "auto",
    numResults: limit,
    contents: { highlights: true },
  });

  return {
    query: query.trim(),
    results: (response.results ?? []).map((result) => ({
      title: result.title ?? "",
      url: result.url,
      publishedDate: result.publishedDate ?? null,
      author: result.author ?? null,
      highlights: result.highlights ?? [],
      highlightScores: result.highlightScores ?? [],
    })),
  };
}

function errorMessage(error) {
  const message = error instanceof Error ? error.message : String(error);
  const apiKey = process.env.EXA_API_KEY;
  return apiKey ? message.replaceAll(apiKey, "[redacted]") : message;
}

async function main() {
  const args = process.argv.slice(2);
  let numResults = 5;
  const words = [];

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--num-results") {
      numResults = Number(args[++i]);
    } else {
      words.push(args[i]);
    }
  }

  const query = words.join(" ").trim();
  if (!query) {
    console.error('Usage: npm run search -- "your search query" [--num-results 5]');
    process.exitCode = 1;
    return;
  }

  try {
    const output = await searchWeb(query, { numResults });
    console.log(JSON.stringify(output, null, 2));
  } catch (error) {
    console.error(`Exa search failed: ${errorMessage(error)}`);
    process.exitCode = 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main();
}
