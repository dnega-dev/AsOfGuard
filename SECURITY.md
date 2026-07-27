# Security policy

## Supported versions

Until the first stable release, security fixes are applied to the latest `0.x` release and the current main development line only.

| Version | Supported |
| --- | --- |
| latest `0.x` | yes |
| older snapshots | no |

## Reporting a vulnerability

Please report suspected vulnerabilities privately to the project maintainers through the private security-reporting channel of the distribution or hosting service from which you obtained AsOfGuard. Do not include sensitive traces in a public issue.

Include, when possible:

- affected AsOfGuard version and Python version;
- operating system and invocation;
- minimal redacted JSONL input;
- observed impact and expected behavior;
- whether the issue exposes trace content, escapes intended output paths, causes unbounded resource use, or misclassifies temporal evidence.

Maintainers should acknowledge a complete report within seven days, provide an assessment or request for more information within fourteen days, and coordinate disclosure after a fix is available. These are targets, not a warranty.

## Threat model

Trace files are untrusted input. AsOfGuard:

- parses JSON with the Python standard library;
- never evaluates trace content as code;
- does not make network requests;
- does not load plugins;
- does not follow document or metadata URLs;
- reads the explicitly selected trace and writes only to an explicitly selected output path;
- emits XML using `xml.etree.ElementTree`, which escapes trace-controlled text.

AsOfGuard does not currently impose input-size, line-length, record-count, nesting-depth, or string-length limits. Operators processing attacker-controlled traces should enforce limits before invocation and run with ordinary least-privilege filesystem controls. Extremely large inputs may consume significant memory because a complete trace is retained for cross-record verification.

## Integrity limitations

AsOfGuard verifies the consistency of supplied evidence; it does not attest that a producer told the truth. For high-assurance deployments, sign trace records, store immutable source-version hashes, use a trusted clock, and bind artifact digests to build provenance.

A clean observable trace is not proof that opaque model weights contain no post-cutoff knowledge. This limitation is part of the product's security and assurance boundary and must not be removed from reports.
