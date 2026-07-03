---
name: test-clash-verge-nodes
description: Use when the user asks to test current Clash Verge or Mihomo proxy nodes, reproduce MiaoKo/MiaoSpeed-style node speed charts, compare latency/speed/unlock status, analyze proxy exit IP/geolocation/ASN, or diagnose MiaoSpeed node-test failures such as unsupported Vless/Hysteria2 parsing.
---

# Test Clash Verge Nodes

## Overview

Use this skill to produce a local, evidence-backed node test report for the user's current Clash Verge setup. Treat MiaoSpeed as the measurement backend for speed/unlock checks and Mihomo/Clash Verge as the live source of truth for currently loaded nodes. For exit analysis, measure the IP, GeoIP country/region/city, ASN, and organization that outside services see through each node.

Do not mutate subscriptions, profiles, proxy groups, or Clash Verge settings. Temporary node payload files contain credentials: keep them in `/tmp`, remove them before finishing, and never include payloads, passwords, UUIDs, server secrets, or subscription URLs in the final report.

## Source Of Truth

Verify current state instead of trusting memory or old notes:

```bash
ps aux | rg -i 'clash|mihomo|verge' | rg -v 'rg -i'
lsof -nP -iTCP -sTCP:LISTEN | rg -i 'clash|mihomo|verge|789|909|1909'
```

For Clash Verge Rev on macOS, the real core often looks like:

```text
/Applications/Clash Verge.app/Contents/MacOS/verge-mihomo \
  -d ~/Library/Application Support/io.github.clash-verge-rev.clash-verge-rev \
  -f ~/Library/Application Support/io.github.clash-verge-rev.clash-verge-rev/clash-verge.yaml \
  -ext-ctl-unix /tmp/verge/verge-mihomo.sock
```

Prefer the live external controller:

```bash
curl --unix-socket /tmp/verge/verge-mihomo.sock -sS http://unix/version
curl --unix-socket /tmp/verge/verge-mihomo.sock -sS http://unix/proxies
```

If there is no Unix socket, read `external-controller`, `mixed-port`, and `secret` from the active config. Redact `secret` in all logs and summaries.

## Tooling

Use the official archived MiaoSpeed release unless the user provides another backend:

- Repo: `miaokobot/miaospeed`
- Known release: `v4.3.1`
- On Apple Silicon, use `miaospeed_4.3.1_darwin_arm64.tar.gz`
- Prefer `miaospeed.meta`; it handles more Clash.Meta-era config than plain `miaospeed`, but it still does not parse every modern protocol.

Download into a local app/work directory, not a global binary path, and verify checksum:

```bash
mkdir -p /Users/yi/apps/miaospeed-4.3.1
gh release download v4.3.1 -R miaokobot/miaospeed \
  -p miaospeed_4.3.1_darwin_arm64.tar.gz \
  -p miaospeed_4.3.1_checksums.txt \
  -D /Users/yi/apps/miaospeed-4.3.1 --clobber
shasum -a 256 /Users/yi/apps/miaospeed-4.3.1/miaospeed_4.3.1_darwin_arm64.tar.gz
rg 'darwin_arm64' /Users/yi/apps/miaospeed-4.3.1/miaospeed_4.3.1_checksums.txt
tar -xzf /Users/yi/apps/miaospeed-4.3.1/miaospeed_4.3.1_darwin_arm64.tar.gz \
  -C /Users/yi/apps/miaospeed-4.3.1
```

For unlock scripts, use `CloudPassenger/miaospeed-scripts` release assets. Start with lightweight/global checks such as YouTube and ChatGPT. Netflix can timeout or return an empty script result and should be a separate optional pass.

## Node Extraction

Use the active merged Clash Verge config, not stale provider files. With macOS Ruby:

```ruby
require 'yaml'
require 'json'

path = '/Users/yi/Library/Application Support/io.github.clash-verge-rev.clash-verge-rev/clash-verge.yaml'
data = YAML.load_file(path)
skip_re = /(剩余流量|套餐到期|距离下次|建议：|官网|官网[:：]|官网https)/
allowed = %w[ss ssr snell socks5 http vmess trojan vless hysteria hysteria2]
nodes = []
(data['proxies'] || []).each do |p|
  name = p['name'].to_s
  type = p['type'].to_s.downcase
  next if name.match?(skip_re)
  next unless allowed.include?(type)
  nodes << { name: name, type: type, payload: p.to_yaml }
end
File.write('/tmp/miaospeed-clash-nodes.json', JSON.pretty_generate(nodes))
puts JSON.generate({selected_nodes: nodes.length})
```

Delete `/tmp/miaospeed-clash-nodes.json` before finishing.

## Test Strategy

Use two tracks and keep the report explicit about which one produced each field.

1. **MiaoSpeed native track**: Use MiaoSpeed's built-in `Clash` vendor for protocols it can parse, usually Trojan/Vmess/SS-era payloads. It can return RTT, HTTP ping, speed, and script results.
2. **Mihomo API track**: Use the live Clash Verge/Mihomo API for modern protocols that MiaoSpeed cannot parse, especially `vless` and `hysteria2`. API delay proves current-core reachability, not MiaoSpeed compatibility.

Do not label a Vless/Hysteria2 node as broken merely because MiaoSpeed says:

```text
Vendor Parser | Parse clash profile error, error=unsupport proxy type: vless
Vendor Parser | Parse clash profile error, error=unsupport proxy type: hysteria2
```

Label it as `unsupported-by-native-vendor` and include Mihomo API delay if available.

## Running MiaoSpeed

Start the backend on a temporary local port:

```bash
MIAOKO_SCRIPT_CONCURRENCY=8 \
/Users/yi/apps/miaospeed-4.3.1/miaospeed.meta server \
  -bind 127.0.0.1:23456 \
  -token local-test-token \
  -connthread 16 \
  -pausesecond 0 \
  -verbose
```

Stop it before finishing and verify no listener remains:

```bash
lsof -nP -iTCP:23456 -sTCP:LISTEN
```

## Request Client Pitfalls

When writing a Node/Python client for the WebSocket API:

- Connect to `ws://127.0.0.1:23456`.
- Actual request uses `Vendor: "Clash"`.
- Signature input must mimic MiaoSpeed's `SlaveRequest.Clone()` behavior: `Vendor` is omitted/empty in the signed JSON even though the actual request includes it.
- Signature is sensitive to Go struct field order.
- MiaoSpeed uses `jsoniter.MarshalToString`; escape `<`, `>`, and `&` as `\u003c`, `\u003e`, and `\u0026` before signing script content.
- Extract the build token from the binary if needed:

```bash
strings -a /Users/yi/apps/miaospeed-4.3.1/miaospeed.meta | rg 'MIAOKO[0-9]'
```

For script tests:

- Add scripts under `Configs.Scripts` as `{ID, Type:"media", Content, TimeoutMillis}`.
- Add matching matrices as `{Type:"TEST_SCRIPT", Params: ID}`.
- Use `TEST_PING_RTT`, `TEST_PING_CONN`, `SPEED_AVERAGE`, and `SPEED_MAX` for core measurements.

Result ordering is not stable. MiaoSpeed pushes `Result.Results` asynchronously; always map node results from `Progress.Index` instead of assuming result array order matches request node order.

## Mihomo Delay

For every node, use the current Clash Verge controller as a cross-check:

```bash
curl --unix-socket /tmp/verge/verge-mihomo.sock -sS \
  "http://unix/proxies/$(python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=\"\"))' \"$NODE\")/delay?timeout=10000&url=http%3A%2F%2Fgstatic.com%2Fgenerate_204"
```

Keep raw API errors such as `Timeout` or `An error occurred in the delay test` in the report. A delay API error can disagree with MiaoSpeed core metrics; report both instead of forcing one verdict.

If you need to test modern protocols through a controlled local proxy, start a separate temporary Mihomo instance with a `/tmp` config and ports such as `19090/19091`. Do not reuse or rewrite the user's live Clash Verge profile. Stop the temporary core and remove its `/tmp` config before finishing.

## Exit Analysis

Exit analysis (测出口 / 出口分析) answers a different question from speed tests: "what IP/ASN/geography does the public Internet see for this node right now?" Do not infer exit from the node name alone. A node named Hong Kong can exit from the United States if its provider routes traffic that way.

Prefer the least invasive path first:

1. Build a temporary Mihomo config under `/tmp`, with one selector such as `EXIT_TEST`, a local HTTP proxy port such as `19190`, and the extracted node payloads.
2. Query an external IP API through `http://127.0.0.1:19190` for each selected node.
3. Stop the temporary core and remove `/tmp` files.

If the temporary core cannot reach provider ingress nodes while the user's live Clash Verge core (主核心) has healthy delay results, do not call the nodes broken. The temporary process can differ from the live service because of privileges, stack options, root-owned runtime state, or provider assumptions. In that case, use the live core with a reversible selector switch:

1. Read and save the original selected proxy for `Proxies` and any relevant groups the user depends on, such as `US` or `OpenAI`.
2. For each node, `PUT /proxies/Proxies` to that node through the Unix socket controller, then run the exit query through the live mixed port, usually `http://127.0.0.1:7890`.
3. Use a `try`/`finally` style cleanup so the original `Proxies` selection is restored even when one node errors.
4. After the run, verify and report `Proxies now: <original node>`; this is the "恢复原选择" check.

Use multiple exit APIs as fallbacks because rate limits and TLS behavior vary by route:

- `ipinfo.io` is useful but can return `429` during repeated tests.
- `ipwho.is` and `api.ip.sb` can fail TLS handshakes on some routes.
- `ip-api.com/json/?fields=status,message,countryCode,regionName,city,query,as,asname,isp,org` is a practical HTTP fallback. Treat its GeoIP as a database snapshot, not physical proof.

For each node, record at least:

- Node name and protocol.
- Mihomo delay result or raw delay error.
- Exit query status, error text, IP, country code, region, city.
- ASN and organization fields from the provider, for example `as`, `asname`, `isp`, and `org`.
- Whether the node-name country matches the measured exit country.

Aggregate the report by country and ASN/organization. Highlight mismatches, such as an `HKG` node whose measured exit is `US / AS132110 / DMIT Inc`. Keep failed nodes in a separate section instead of hiding them.

## Report Contract

Write Markdown plus CSV/JSON when practical. The report should include:

- Tool versions and timestamp.
- Node count by protocol.
- Which rows came from MiaoSpeed native vs Mihomo API.
- Latency fields: Clash/Mihomo API delay, MiaoSpeed RTT, MiaoSpeed HTTP ping.
- Speed fields: short-test average and max, with units and duration.
- Unlock fields used, for example YouTube and ChatGPT.
- Exit fields when requested: IP, country, region, city, ASN, AS organization, ISP/org, and node-name-country mismatch.
- Explicit statuses such as `ok`, `unsupported-by-native-vendor`, `parse-or-test-failed`.
- Limitations: short speed tests are snapshots, not long-duration benchmarks; GeoIP/ASN services are snapshots of external databases and can disagree with provider marketing or physical routing.

Never include node payloads, server passwords, UUIDs, subscriptions, or provider URLs in reports.

## Cleanup Checklist

Before the final response:

```bash
rm -rf /tmp/miaospeed-clash-nodes.json /tmp/miaospeed-mihomo /tmp/clash-exit-analysis
lsof -nP -iTCP:19090 -iTCP:19091 -iTCP:19190 -iTCP:19191 -iTCP:23456 -sTCP:LISTEN
ps aux | rg -i 'miaospeed|verge-mihomo -d /tmp/(miaospeed|clash-exit-analysis)' | rg -v 'rg -i'
```

If the live core was temporarily switched, verify the `Proxies` group was restored before finishing. Final response should give report paths, counts, major caveats, and the highest-signal rankings or exit mismatches. Mention any protocols that MiaoSpeed did not natively support.
