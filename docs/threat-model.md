# Prototype threat model

The finite prototype assumes that the operating system, SQLite file permissions, HMAC secrets, trusted permit issuer, and evaluator process are not controlled by the acting model. It does not claim protection when an attacker can alter the Python source, read the shared HMAC key, directly modify the database, or invoke trusted issuer code.

The executor checks an action against an HMAC permit bound to the action, destination, complete state, and persisted policy. It consumes a nonce and advances the local snapshot in one SQLite transaction. Its local effect record is idempotent. A real external receiver must independently deduplicate the nonce and support reconciliation after crashes.

Signed exports bind state, policy, clock, completed effects, and pending dispatch metadata. They are integrity-protected, not automatically fresh or authoritative. A production handoff needs an authenticated source, monotonic epochs, an import protocol, and receiver-side effect reconciliation.

The local evaluator process is an interface boundary only. Production evaluator custody requires separate credentials and deployment authority.

## Separation and external effects

The prototype has a separate SQLite-backed effect receiver that deduplicates a nonce before recording a local executor completion. This demonstrates the required receiver contract; it is not a networked production service. The handoff authority records a monotonic epoch per source and rejects signed replays. Its HMAC signer is a test implementation. A production deployment should use an external public-key signer/verifier, distinct operating-system identities, authenticated transport, and durable reconciliation between executor and receiver.
