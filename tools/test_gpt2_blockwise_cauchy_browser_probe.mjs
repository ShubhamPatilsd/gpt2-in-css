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
const experiment = path.join(workspace, "experiments/gpt2-blockwise-cauchy-head");
const reference = JSON.parse(await fs.readFile(path.join(experiment, "reference.json"), "utf8"));
const offline = JSON.parse(await fs.readFile(path.join(experiment, "offline-results.json"), "utf8"));
const pointTimeout = Number(process.env.BLOCKWISE_CAUCHY_POINT_TIMEOUT_MS ?? 60_000);

function finalizeReport(report) {
  for (const groupCount of reference.scaling.groupCounts) {
    const pair = report[`groups${groupCount}`];
    if (pair.control.status === "ok" && pair.blockwise.status === "ok") {
      pair.firstLayoutRatio = pair.blockwise.firstLayoutMilliseconds
        / pair.control.firstLayoutMilliseconds;
      pair.mutationRatio = pair.blockwise.mutationMilliseconds
        / pair.control.mutationMilliseconds;
      pair.decisivelySlower = (
        pair.blockwise.firstLayoutMilliseconds - pair.control.firstLayoutMilliseconds > 1000
          && pair.firstLayoutRatio >= 2
      ) || (
        pair.blockwise.mutationMilliseconds - pair.control.mutationMilliseconds > 100
          && pair.mutationRatio >= 2
      );
    } else {
      pair.decisivelySlower = pair.blockwise.status !== "ok";
    }
  }
  const globalOffline = offline.configurations.find(({ blockCount }) => blockCount === 1);
  const blockwiseOffline = offline.configurations.find(({ blockCount }) => blockCount === 96);
  report.offlineExactGroups = {
    global: globalOffline.bestFirstExactGroups,
    blockwise96: blockwiseOffline.bestFirstExactGroups,
  };
  const extraMutationMilliseconds = report.groups64.blockwise.mutationMilliseconds
    - report.groups64.control.mutationMilliseconds;
  const sameFontOneGroupUpperMilliseconds = report.groups1.control.mutationMilliseconds;
  report.payoffGate = {};
  for (const split of ["validation", "test"]) {
    const exactGroupsSaved = globalOffline.bestFirstExactGroups[split].mean
      - blockwiseOffline.bestFirstExactGroups[split].mean;
    report.payoffGate[split] = {
      exactGroupsSaved,
      extraCoarseMutationMilliseconds: extraMutationMilliseconds,
      breakEvenMillisecondsPerExactGroup: extraMutationMilliseconds / exactGroupsSaved,
      sameFontOneGroupUpperMilliseconds,
      maximumCreditableSavingsMilliseconds:
        exactGroupsSaved * sameFontOneGroupUpperMilliseconds,
      paysUnderSameFontUpperBound:
        exactGroupsSaved * sameFontOneGroupUpperMilliseconds > extraMutationMilliseconds,
    };
  }
  report.decision = report.groups64.decisivelySlower
      || !report.payoffGate.validation.paysUnderSameFontUpperBound
      || !report.payoffGate.test.paysUnderSameFontUpperBound
    ? "reject-live-96-block-browser-carrier-retain-theoretical-bound"
    : "retain-for-integrated-cascade-test";
  return report;
}

function dimensionsFor(groupCount) {
  return {
    expectedGroups: groupCount,
    expectedCandidates: groupCount * reference.scaling.rowsPerFullGroup,
  };
}

async function workerMain() {
  const kind = process.argv[3];
  const groupCount = Number(process.argv[4]);
  const baseUrl = process.argv[5];
  const { expectedGroups, expectedCandidates } = dimensionsFor(groupCount);
  const browser = await chromium.launch({ executablePath, headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 320, height: 120 } });
    const page = await context.newPage();
    const started = performance.now();
    await page.goto(
      `${baseUrl}/experiments/gpt2-blockwise-cauchy-head/scaling/${kind}-${groupCount}.html`,
      { waitUntil: "domcontentloaded" },
    );
    await page.waitForFunction(() => document.fonts.status === "loaded");
    const before = await page.locator(".group-wrapper").evaluateAll((elements) => {
      const compute = getComputedStyle(document.querySelector(".compute-values"));
      const stage = getComputedStyle(document.querySelector(".score-stage"));
      const bound = document.querySelector(".bound-glyph");
      const scoreVariation = stage.fontVariationSettings;
      const boundVariation = bound ? getComputedStyle(bound).fontVariationSettings : "normal";
      return {
        groupCount: elements.length,
        candidateCount: document.querySelectorAll(".candidate").length,
        widths: elements.map((element) => element.getBoundingClientRect().width),
        candidateWidths: [...document.querySelectorAll(".candidate")]
          .slice(0, 4).map((element) => element.getBoundingClientRect().width),
        computed: {
          h0: compute.getPropertyValue("--h0"),
          queryNorm: compute.getPropertyValue("--query-norm"),
          bn0: compute.getPropertyValue("--bn0"),
          bn95: compute.getPropertyValue("--bn95"),
          scoreVariationIsNormal: scoreVariation === "normal",
          scoreVariationAxisCount: (scoreVariation.match(/"/g) ?? []).length / 2,
          boundVariationIsNormal: boundVariation === "normal",
          boundVariationAxisCount: (boundVariation.match(/"/g) ?? []).length / 2,
          boundVariationHead: boundVariation.slice(0, 96),
          boundBn0: bound ? getComputedStyle(bound).getPropertyValue("--bn0") : "",
          boundRulePresent: [...document.styleSheets].flatMap((sheet) => [...sheet.cssRules])
            .some((rule) => rule.selectorText === ".bound-glyph"
              && rule.style.fontVariationSettings !== ""),
          supportsBoundLiteral: CSS.supports("font-variation-settings", '"b000" 0.1'),
        },
      };
    });
    const firstLayoutMilliseconds = performance.now() - started;
    process.stdout.write(`FIRST ${JSON.stringify({ firstLayoutMilliseconds })}\n`);

    const mutationStarted = performance.now();
    const after = await page.locator("#model").evaluate((model, fixture) => {
      fixture.hidden.forEach((value, dimension) => {
        model.style.setProperty(`--h${dimension}`, String(value));
      });
      model.style.setProperty("--score-offset", `${-fixture.floor * 256 * 4}px`);
      const widths = [...document.querySelectorAll(".group-wrapper")]
        .map((element) => element.getBoundingClientRect().width);
      const compute = getComputedStyle(document.querySelector(".compute-values"));
      const stage = getComputedStyle(document.querySelector(".score-stage"));
      const bound = document.querySelector(".bound-glyph");
      const scoreVariation = stage.fontVariationSettings;
      const boundVariation = bound ? getComputedStyle(bound).fontVariationSettings : "normal";
      return {
        widths,
        candidateWidths: [...document.querySelectorAll(".candidate")]
          .slice(0, 4).map((element) => element.getBoundingClientRect().width),
        computed: {
          h0: compute.getPropertyValue("--h0"),
          queryNorm: compute.getPropertyValue("--query-norm"),
          bn0: compute.getPropertyValue("--bn0"),
          bn95: compute.getPropertyValue("--bn95"),
          scoreVariationIsNormal: scoreVariation === "normal",
          scoreVariationAxisCount: (scoreVariation.match(/"/g) ?? []).length / 2,
          boundVariationIsNormal: boundVariation === "normal",
          boundVariationAxisCount: (boundVariation.match(/"/g) ?? []).length / 2,
          boundVariationHead: boundVariation.slice(0, 96),
          boundBn0: bound ? getComputedStyle(bound).getPropertyValue("--bn0") : "",
          boundRulePresent: [...document.styleSheets].flatMap((sheet) => [...sheet.cssRules])
            .some((rule) => rule.selectorText === ".bound-glyph"
              && rule.style.fontVariationSettings !== ""),
          supportsBoundLiteral: CSS.supports("font-variation-settings", '"b000" 0.1'),
        },
      };
    }, {
      hidden: reference.fixtures.hiddenVectors[reference.scaling.mutationFixture],
      floor: reference.fixtures.scoreFloors[reference.scaling.mutationFixture],
    });
    const mutationMilliseconds = performance.now() - mutationStarted;
    const changedGroups = before.widths.reduce(
      (count, width, index) => count + Number(width !== after.widths[index]),
      0,
    );
    const result = {
      status: "ok",
      kind,
      groupCount,
      ...dimensionsFor(groupCount),
      observedGroups: before.groupCount,
      observedCandidates: before.candidateCount,
      structureCorrect: before.groupCount === expectedGroups
        && before.candidateCount === expectedCandidates,
      firstLayoutMilliseconds,
      mutationMilliseconds,
      changedGroups,
      changedProbeCandidates: before.candidateWidths.reduce(
        (count, width, index) => count + Number(width !== after.candidateWidths[index]),
        0,
      ),
      computedBefore: before.computed,
      computedAfter: after.computed,
      maxWidthBefore: Math.max(...before.widths),
      maxWidthAfter: Math.max(...after.widths),
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

if (process.argv[2] === "--finalize-existing") {
  const existing = JSON.parse(
    await fs.readFile(path.join(experiment, "browser-results.json"), "utf8"),
  );
  finalizeReport(existing);
  await fs.writeFile(
    path.join(experiment, "browser-results.json"),
    `${JSON.stringify(existing, null, 2)}\n`,
  );
  console.log(JSON.stringify({ decision: existing.decision, payoffGate: existing.payoffGate }, null, 2));
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
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
      consumeLines();
    });
    child.stderr.on("data", (chunk) => { stderr += chunk; });
    child.on("error", (error) => finish({
      status: "worker-error", kind, groupCount, error: error.message,
    }));
    child.on("close", (code, signal) => {
      consumeLines();
      if (!settled) finish({
        status: "worker-error",
        kind,
        groupCount,
        code,
        signal,
        stderr: stderr.slice(-2000),
      });
    });
    armTimer();
  });
}

const report = {
  scope: reference.scaling.scope,
  fullGate: {
    status: "failed",
    reason: "candidate first/full layout exceeded 180 seconds",
    retried: false,
  },
  groupCounts: reference.scaling.groupCounts,
  pointTimeoutMilliseconds: pointTimeout,
  fixtureSelection: {
    initial: reference.scaling.initialFixture,
    mutation: reference.scaling.mutationFixture,
    method: reference.scaling.fixtureSelection,
  },
  points: [],
};

try {
  for (const groupCount of reference.scaling.groupCounts) {
    const order = groupCount === 4 || groupCount === 64
      ? ["blockwise", "control"]
      : ["control", "blockwise"];
    const pair = { groupCount, order };
    for (const kind of order) {
      pair[kind] = await runPoint(kind, groupCount);
      report.points.push(pair[kind]);
      await fs.writeFile(
        path.join(experiment, "browser-results.json"),
        `${JSON.stringify(report, null, 2)}\n`,
      );
    }
    report[`groups${groupCount}`] = pair;
  }
  finalizeReport(report);
} finally {
  server.closeAllConnections();
  await new Promise((resolve) => server.close(resolve));
}

await fs.writeFile(
  path.join(experiment, "browser-results.json"),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
if (report.points.some((point) => point.status === "worker-error" || point.structureCorrect === false)) {
  process.exitCode = 1;
}
