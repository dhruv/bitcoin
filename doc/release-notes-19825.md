### RPC and other APIs
- #19825 `setban` behavior changed. Banning a subnet that is a subset of a previous ban for a shorter duration is a no-op. Banning a subnet that is a superset of a previous ban for a longer duration will result in ban entry consolidation.
