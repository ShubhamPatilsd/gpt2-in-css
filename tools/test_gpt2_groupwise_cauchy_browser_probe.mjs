import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { spawn } from "node:child_process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const workspace = path.resolve(new URL("..", import.meta.url).pathname);
const experiment = path.join(workspace, "experiments/gpt2-groupwise-cauchy-head");
const reference = JSON.parse(await fs.readFile(path.join(experiment, "reference.json"), "utf8"));
const offline = JSON.parse(await fs.readFile(path.join(experiment, "offline-results.json"), "utf8"));
const prior = JSON.parse(await fs.readFile(
  path.join(workspace, "experiments/gpt2-blockwise-cauchy-head/offline-results.json"),
  "utf8",
));
const pointTimeout = Number(process.env.GROUPWISE_CAUCHY_POINT_TIMEOUT_MS ?? 60_000);

function median(values) {
  const ordered = [...values].sort((a, b) => a - b);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2
    ? ordered[middle]
    : (ordered[middle - 1] + ordered[middle]) / 2;
}

function offlineConfiguration(source, blockCount) {
  return source.configurations.find((row) => row.blockCount === blockCount);
}

function expectedCandidates(groupCount) {
  return Math.min(groupCount * reference.scaling.rowsPerFullGroup, offline.vocabulary);
}

function dimensionsFor(kind, groupCount) {
  return {
    expectedGroups: groupCount,
    expectedCandidates: expectedCandidates(groupCount),
    expectedBounds: kind === "groupwise" ? groupCount : 0,
  };
}

async function workerMain() {
  const kind = process.argv[3];
  const groupCount = Number(process.argv[4]);
  const baseUrl = process.argv[5];
  const dimensions = dimensionsFor(kind, groupCount);
  const browser = await chromium.launch({ executablePath, headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 320, height: 120 } });
    const page = await context.newPage();
    const started = performance.now();
    await page.goto(
      `${baseUrl}/experiments/gpt2-groupwise-cauchy-head/scaling/${kind}-${groupCount}.html`,
      { waitUntil: "domcontentloaded", timeout: pointTimeout },
    );
    await page.waitForFunction(() => document.fonts.status === "loaded");
    const before = await page.locator("#model").evaluate(() => {
      const compute = getComputedStyle(document.querySelector(".compute-values"));
      const stage = getComputedStyle(document.querySelector(".score-stage"));
      const bound = document.querySelector(".group-bound");
      const boundStyle = bound ? getComputedStyle(bound) : null;
      const variation = boundStyle?.fontVariationSettings ?? "normal";
      return {
        groups: document.querySelectorAll(".group-wrapper").length,
        candidates: document.querySelectorAll(".candidate").length,
        bounds: document.querySelectorAll(".group-bound").length,
        groupWidths: [...document.querySelectorAll(".group-wrapper")]
          .map((element) => element.getBoundingClientRect().width),
        boundWidths: [...document.querySelectorAll(".group-bound")]
          .map((element) => element.getBoundingClientRect().width),
        diagnostics: {
          h0: Number(compute.getPropertyValue("--h0")),
          blockNorms: Array.from({ length: 96 }, (_, block) =>
            Number(compute.getPropertyValue(`--bn${block}`))),
          scoreVariationAxisCount: (stage.fontVariationSettings.match(/"/g) ?? []).length / 2,
          boundVariationIsNormal: variation === "normal",
          boundVariationAxisCount: (variation.match(/"/g) ?? []).length / 2,
          boundVariation: variation,
          boundFontFamily: boundStyle?.fontFamily ?? "",
        },
      };
    });
    const firstLayoutMilliseconds = performance.now() - started;
    process.stdout.write(`FIRST ${JSON.stringify({ firstLayoutMilliseconds })}\n`);

    const initialFixture = reference.scaling.initialFixture;
    const mutationFixture = reference.scaling.mutationFixture;
    const mutationTimes = [];
    let after = null;
    for (let iteration = 0; iteration < reference.scaling.mutationIterations; iteration += 1) {
      const fixture = iteration % 2 === 0 ? mutationFixture : initialFixture;
      const mutationStarted = performance.now();
      after = await page.locator("#model").evaluate((model, payload) => {
        payload.hidden.forEach((value, dimension) => {
          model.style.setProperty(`--h${dimension}`, String(value));
        });
        model.style.setProperty("--score-offset", `${-payload.floor * 256 * 4}px`);
        const compute = getComputedStyle(document.querySelector(".compute-values"));
        const stage = getComputedStyle(document.querySelector(".score-stage"));
        const bound = document.querySelector(".group-bound");
        const boundStyle = bound ? getComputedStyle(bound) : null;
        const variation = boundStyle?.fontVariationSettings ?? "normal";
        return {
          groupWidths: [...document.querySelectorAll(".group-wrapper")]
            .map((element) => element.getBoundingClientRect().width),
          boundWidths: [...document.querySelectorAll(".group-bound")]
            .map((element) => element.getBoundingClientRect().width),
          diagnostics: {
            h0: Number(compute.getPropertyValue("--h0")),
            blockNorms: Array.from({ length: 96 }, (_, block) =>
              Number(compute.getPropertyValue(`--bn${block}`))),
            scoreVariationAxisCount: (stage.fontVariationSettings.match(/"/g) ?? []).length / 2,
            boundVariationIsNormal: variation === "normal",
            boundVariationAxisCount: (variation.match(/"/g) ?? []).length / 2,
            boundVariation: variation,
            boundFontFamily: boundStyle?.fontFamily ?? "",
          },
        };
      }, {
        hidden: reference.fixtures.hiddenVectors[fixture],
        floor: reference.fixtures.scoreFloors[fixture],
      });
      mutationTimes.push(performance.now() - mutationStarted);
    }
    const changedBlockNorms = kind === "groupwise"
      ? before.diagnostics.blockNorms.reduce(
        (count, value, index) => count + Number(value !== after.diagnostics.blockNorms[index]),
        0,
      )
      : null;
    const changedBoundAxes = kind === "groupwise"
      ? (() => {
        const beforeValues = new Map([...before.diagnostics.boundVariation.matchAll(/"(b\d{3})"\s+([\d.eE+-]+)/g)]
          .map((match) => [match[1], Number(match[2])]));
        const afterValues = new Map([...after.diagnostics.boundVariation.matchAll(/"(b\d{3})"\s+([\d.eE+-]+)/g)]
          .map((match) => [match[1], Number(match[2])]));
        return Array.from({ length: 96 }, (_, block) => `b${String(block).padStart(3, "0")}`)
          .reduce((count, tag) => count + Number(
            beforeValues.has(tag) && afterValues.has(tag)
              && beforeValues.get(tag) !== afterValues.get(tag)
          ), 0);
      })()
      : null;
    const expectedBoundPixelsBefore = kind === "groupwise"
      ? reference.fixtures.browserGroupRadiusPixels[
        reference.scaling.initialFixture
      ].slice(0, Math.min(8, groupCount)) : [];
    const expectedBoundPixelsAfter = kind === "groupwise"
      ? reference.fixtures.browserGroupRadiusPixels[
        reference.scaling.mutationFixture
      ].slice(0, Math.min(8, groupCount)) : [];
    const outwardBucket = (value) => Math.floor((value + 4) / 4) * 4;
    const measuredBoundWidthsBefore = before.boundWidths.slice(0, 8);
    const measuredBoundWidthsAfter = after.boundWidths.slice(0, 8);
    const boundGeometryMatchesExpected = kind === "groupwise"
      ? expectedBoundPixelsBefore.every((value, index) =>
        Math.abs(measuredBoundWidthsBefore[index] - outwardBucket(value)) < 0.02)
        && expectedBoundPixelsAfter.every((value, index) =>
          Math.abs(measuredBoundWidthsAfter[index] - outwardBucket(value)) < 0.02)
      : null;
    const result = {
      status: "ok",
      kind,
      groupCount,
      ...dimensions,
      observedGroups: before.groups,
      observedCandidates: before.candidates,
      observedBounds: before.bounds,
      structureCorrect: before.groups === dimensions.expectedGroups
        && before.candidates === dimensions.expectedCandidates
        && before.bounds === dimensions.expectedBounds,
      firstLayoutMilliseconds,
      mutationMilliseconds: median(mutationTimes),
      mutationTimesMilliseconds: mutationTimes,
      changedGroups: before.groupWidths.reduce(
        (count, width, index) => count + Number(width !== after.groupWidths[index]), 0,
      ),
      changedBounds: before.boundWidths.reduce(
        (count, width, index) => count + Number(width !== after.boundWidths[index]), 0,
      ),
      boundWidthsBefore: measuredBoundWidthsBefore,
      boundWidthsAfter: measuredBoundWidthsAfter,
      expectedBoundPixelsBefore,
      expectedBoundPixelsAfter,
      expectedOutwardBucketsBefore: expectedBoundPixelsBefore.map(outwardBucket),
      expectedOutwardBucketsAfter: expectedBoundPixelsAfter.map(outwardBucket),
      boundGeometryMatchesExpected,
      changedBlockNorms,
      changedBoundAxes,
      allBlockNormsLive: kind === "groupwise" ? changedBlockNorms === 96 : null,
      allBoundAxesLive: kind === "groupwise" ? changedBoundAxes === 96 : null,
      computedBefore: before.diagnostics,
      computedAfter: after.diagnostics,
      maxWidthBefore: Math.max(...before.groupWidths),
      maxWidthAfter: Math.max(...after.groupWidths),
      chrome: await browser.version(),
    };
    process.stdout.write(`RESULT ${JSON.stringify(result)}\n`);
    await context.close();
  } finally {
    await browser.close();
  }
}

if (process.argv[2] === "--worker") {
  await workerMain();
  process.exit(0);
}

const types = new Map([
  [".html", "text/html"], [".css", "text/css"], [".woff2", "font/woff2"],
]);
const server = http.createServer(async (request, response) => {
  try {
    const filename = path.join(
      workspace,
      decodeURIComponent(new URL(request.url, "http://x").pathname),
    );
    if (!filename.startsWith(`${workspace}${path.sep}`)) throw new Error("outside workspace");
    const body = await fs.readFile(filename);
    response.writeHead(200, {
      "content-type": types.get(path.extname(filename)) ?? "application/octet-stream",
      "cache-control": "no-store",
    });
    response.end(body);
  } catch {
    response.writeHead(404).end();
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const baseUrl = `http://127.0.0.1:${server.address().port}`;

function killWorkerGroup(child) {
  try {
    process.kill(-child.pid, "SIGKILL");
  } catch (error) {
    if (error.code !== "ESRCH") throw error;
  }
}

async function runPoint(kind, groupCount) {
  return new Promise((resolve) => {
    const child = spawn(
      process.execPath,
      [new URL(import.meta.url).pathname, "--worker", kind, String(groupCount), baseUrl],
      { detached: true, stdio: ["ignore", "pipe", "pipe"] },
    );
    let stdout = "";
    let stderr = "";
    let sawFirstLayout = false;
    let firstLayoutMilliseconds = null;
    let settled = false;
    let timer;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(value);
    };
    const armTimer = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        killWorkerGroup(child);
        finish({
          status: sawFirstLayout ? "mutation-timeout" : "first-layout-timeout",
          kind,
          groupCount,
          timeoutMilliseconds: pointTimeout,
          firstLayoutMilliseconds,
        });
      }, pointTimeout);
    };
    const consumeLines = () => {
      const lines = stdout.split("\n");
      stdout = lines.pop();
      for (const line of lines) {
        if (line.startsWith("FIRST ")) {
          const first = JSON.parse(line.slice(6));
          sawFirstLayout = true;
          firstLayoutMilliseconds = first.firstLayoutMilliseconds;
          armTimer();
        } else if (line.startsWith("RESULT ")) {
          finish(JSON.parse(line.slice(7)));
        }
      }
    };
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk) => { stdout += chunk; consumeLines(); });
    child.stderr.on("data", (chunk) => { stderr += chunk; });
    child.on("error", (error) => finish({
      status: "worker-error", kind, groupCount, error: error.message,
    }));
    child.on("close", (code, signal) => {
      consumeLines();
      if (!settled) finish({
        status: "worker-error", kind, groupCount, code, signal, stderr: stderr.slice(-2000),
      });
    });
    armTimer();
  });
}

const globalOffline = offlineConfiguration(prior, 1);
const groupwiseOffline = offlineConfiguration(offline, 96);
const report = {
  scope: reference.scaling.scope,
  groupCountsPlanned: reference.scaling.groupCounts,
  pointTimeoutMilliseconds: pointTimeout,
  mutationIterations: reference.scaling.mutationIterations,
  fixtureSelection: {
    initial: reference.scaling.initialFixture,
    mutation: reference.scaling.mutationFixture,
    method: reference.scaling.fixtureSelection,
  },
  earlyStop: null,
  points: [],
};

try {
  for (const groupCount of reference.scaling.groupCounts) {
    const order = groupCount === 4 || groupCount === 64
      ? ["groupwise", "control"] : ["control", "groupwise"];
    const pair = { groupCount, order };
    for (const kind of order) {
      pair[kind] = await runPoint(kind, groupCount);
      report.points.push(pair[kind]);
      await fs.writeFile(
        path.join(experiment, "browser-results.json"),
        `${JSON.stringify(report, null, 2)}\n`,
      );
    }
    if (pair.control.status === "ok" && pair.groupwise.status === "ok") {
      pair.firstLayoutRatio = pair.groupwise.firstLayoutMilliseconds
        / pair.control.firstLayoutMilliseconds;
      pair.mutationRatio = pair.groupwise.mutationMilliseconds
        / pair.control.mutationMilliseconds;
    }
    report[`groups${groupCount}`] = pair;

    if (pair.groupwise.status !== "ok") {
      const timedOut = pair.groupwise.status === "first-layout-timeout"
        || pair.groupwise.status === "mutation-timeout";
      report.earlyStop = {
        afterGroupCount: groupCount,
        gate: timedOut ? "performance-timeout" : "worker-failure",
        reason: timedOut
          ? `candidate crossed the authoritative ${pointTimeout}ms point timeout`
          : "candidate worker failed before producing a valid measurement",
      };
      break;
    }
    const invalid = pair.groupwise.structureCorrect === false
      || pair.groupwise.allBlockNormsLive === false
      || pair.groupwise.allBoundAxesLive === false
      || pair.groupwise.changedBounds === 0
      || pair.groupwise.boundGeometryMatchesExpected === false;
    if (invalid) {
      report.earlyStop = {
        afterGroupCount: groupCount,
        gate: "invalid-carrier",
        reason: (
          "structure mismatched, fewer than all 96 norms/axes changed, or measured "
          + "glyph widths disagreed with predicted outward buckets"
        ),
      };
      break;
    }

    if (groupCount === 64) {
      const extraCoarseMutationMilliseconds = pair.groupwise.mutationMilliseconds
        - pair.control.mutationMilliseconds;
      const oneGroupControlMilliseconds = report.groups1.control.mutationMilliseconds;
      report.payoffGate = {};
      for (const split of ["validation", "test"]) {
        const exactGroupsSaved = globalOffline.bestFirstExactGroups[split].mean
          - groupwiseOffline.bestFirstExactGroups[split].mean;
        const maximumCreditableSavingsMilliseconds = exactGroupsSaved
          * oneGroupControlMilliseconds;
        report.payoffGate[split] = {
          exactGroupsSaved,
          extraCoarseMutationMilliseconds,
          breakEvenMillisecondsPerExactGroup:
            extraCoarseMutationMilliseconds / exactGroupsSaved,
          oneGroupControlMilliseconds,
          maximumCreditableSavingsMilliseconds,
          paysUnderSameFontUpperBound:
            extraCoarseMutationMilliseconds <= maximumCreditableSavingsMilliseconds,
        };
      }
      const decisiveSlowdown = extraCoarseMutationMilliseconds > 100
        && pair.mutationRatio >= 2;
      const failsPayoff = !report.payoffGate.validation.paysUnderSameFontUpperBound
        || !report.payoffGate.test.paysUnderSameFontUpperBound;
      if (decisiveSlowdown || failsPayoff) {
        report.earlyStop = {
          afterGroupCount: 64,
          gate: decisiveSlowdown ? "decisive-slowdown" : "payoff",
          reason: decisiveSlowdown
            ? "candidate is at least 2x and over 100ms slower"
            : "extra coarse cost exceeds maximum same-font exact-group savings",
        };
        break;
      }
    }
  }
} finally {
  server.closeAllConnections();
  await new Promise((resolve) => server.close(resolve));
}

if (report.earlyStop?.gate === "invalid-carrier"
    || report.earlyStop?.gate === "worker-failure") {
  report.decision = "reject-invalid-group-bound-carrier";
} else if (report.earlyStop?.gate === "performance-timeout") {
  report.decision = "reject-full-scale-gate";
} else if (report.earlyStop) {
  report.decision = "reject-live-groupwise-carrier-retain-offline-certificate";
} else if (report.groups197?.control.status === "ok"
    && report.groups197?.groupwise.status === "ok") {
  report.decision = "retain-groupwise-carrier-for-integrated-cascade-test";
} else {
  report.decision = "reject-full-scale-gate";
}
await fs.writeFile(
  path.join(experiment, "browser-results.json"),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
if (report.points.some((point) => point.status === "worker-error" || point.structureCorrect === false)) {
  process.exitCode = 1;
}
