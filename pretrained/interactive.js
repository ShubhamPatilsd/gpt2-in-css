const data = await fetch('prompt-data.json').then(response => response.json());
const form = document.querySelector('#prompt-form');
const input = document.querySelector('#prompt');
const stream = document.querySelector('#stream');
const metrics = document.querySelector('#metrics');
const stylesheet = document.querySelector('#model-css');
const root = document.documentElement;
const textEncoder = new TextEncoder();
const steps = 4;
const maximumPromptTokens = 4;

function bytesToUnicode() {
  const bytes = [];
  for (let value = 33; value <= 126; value += 1) bytes.push(value);
  for (let value = 161; value <= 172; value += 1) bytes.push(value);
  for (let value = 174; value <= 255; value += 1) bytes.push(value);
  const codePoints = [...bytes];
  let extra = 0;
  for (let value = 0; value < 256; value += 1) {
    if (!bytes.includes(value)) {
      bytes.push(value);
      codePoints.push(256 + extra);
      extra += 1;
    }
  }
  return new Map(bytes.map((value, index) => [value, String.fromCodePoint(codePoints[index])]));
}

const byteEncoder = bytesToUnicode();
const mergeRanks = new Map(data.merges.map((pair, rank) => [`${pair[0]}\u0000${pair[1]}`, rank]));
const tokenPattern = /'s|'t|'re|'ve|'m|'ll|'d| ?[A-Za-z]+| ?[0-9]+| ?[^\sA-Za-z0-9]+|\s+/g;

function bpe(token) {
  let pieces = [...token];
  while (pieces.length > 1) {
    let bestIndex = -1;
    let bestRank = Number.POSITIVE_INFINITY;
    for (let index = 0; index < pieces.length - 1; index += 1) {
      const rank = mergeRanks.get(`${pieces[index]}\u0000${pieces[index + 1]}`);
      if (rank !== undefined && rank < bestRank) {
        bestRank = rank;
        bestIndex = index;
      }
    }
    if (bestIndex < 0) break;
    pieces = [
      ...pieces.slice(0, bestIndex),
      pieces[bestIndex] + pieces[bestIndex + 1],
      ...pieces.slice(bestIndex + 2),
    ];
  }
  return pieces;
}

function encode(text) {
  const ids = [];
  for (const match of text.matchAll(tokenPattern)) {
    const encoded = [...textEncoder.encode(match[0])].map(byte => byteEncoder.get(byte)).join('');
    for (const piece of bpe(encoded)) ids.push(data.vocab[piece]);
  }
  return ids;
}

function loadGraph(promptLength) {
  const href = `interactive-${promptLength}.css`;
  if (stylesheet.getAttribute('href') === href) return Promise.resolve();
  return new Promise((resolve, reject) => {
    stylesheet.onload = resolve;
    stylesheet.onerror = () => reject(new Error(`Could not load ${href}`));
    stylesheet.setAttribute('href', href);
  });
}

async function generate(event) {
  event?.preventDefault();
  const promptIds = encode(input.value);
  if (promptIds.length < 1 || promptIds.length > maximumPromptTokens) {
    stream.textContent = input.value;
    metrics.textContent = `Prompt is ${promptIds.length} GPT-2 tokens; use 1–${maximumPromptTokens}.`;
    return;
  }

  metrics.textContent = `loading ${promptIds.length}-token CSS graph…`;
  try {
    await loadGraph(promptIds.length);
  } catch (error) {
    metrics.textContent = error.message;
    return;
  }
  promptIds.forEach((token, position) => {
    for (let dimension = 0; dimension < 2; dimension += 1) {
      const value = data.embeddings[token][dimension] + data.positions[position][dimension];
      root.style.setProperty(`--interactive-input-${position}-${dimension}`, value);
    }
  });

  const started = performance.now();
  const styles = getComputedStyle(root);
  const outputIds = [];
  for (let step = 0; step < steps; step += 1) {
    outputIds.push(Math.round(Number.parseFloat(
      styles.getPropertyValue(`--generation-${step}-winner-id`),
    )));
  }
  const elapsed = performance.now() - started;
  if (outputIds.some(token => !Number.isInteger(token) || token < 0 || token >= data.byId.length)) {
    metrics.textContent = 'The browser returned an invalid token ID.';
    return;
  }
  stream.textContent = input.value + outputIds.map(token => data.byId[token]).join('');
  metrics.textContent = `prompt [${promptIds.join(', ')}] → [${outputIds.join(', ')}] · ${(elapsed / steps).toFixed(2)} ms/token`;
}

form.addEventListener('submit', generate);
stream.textContent = 'ready';
generate();
