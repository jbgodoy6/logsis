# PBKDF2 dependency

SJCL 1.0.8, obtained from the official npm registry (`sjcl@1.0.8`), under its BSD-2-Clause option. The upstream copyright/license notice is retained in the vendored source and in Code.gs.

Tarball: https://registry.npmjs.org/sjcl/-/sjcl-1.0.8.tgz
SHA-256: e951881e45a6744e3fa946ebe613e18009ba951bd6a7580e2e450d9d0c893d4f

The vendored file contains the upstream namespace and core/bitArray.js, codecString.js, codecHex.js, sha256.js, hmac.js and pbkdf2.js. Only indentation/trailing whitespace were normalized. It is appended to Code.gs so deployment remains a single paste with no external scripts or runtime downloads.

Used only to verify the developer's actual password at the Google server for account-management operations. PBKDF2-HMAC-SHA256 parameters remain 600,000 iterations, 16-byte salt, 32-byte output, compatible with the existing Python verifiers. Independent Node crypto vectors, Unicode passwords and authenticated management paths are checked by tests/apps_script_contract.cjs.
