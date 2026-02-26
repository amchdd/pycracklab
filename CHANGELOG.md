# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Argon2** — Suporte a Argon2id no benchmark, detecção automática de hash e ataque por wordlist (recomendação atual para senhas).
- **Barra de progresso** — Progress bar (rich) no brute force (incluindo modo multiprocess) e no ataque por wordlist (single e multiprocess).
- **Export de estatísticas** — Opção `--stats-json <arquivo>` para gravar resultado, tentativas, tempo e hashes/s em JSON ao final da execução.
- **CLI `--version`** — Flag para exibir versão do PyCrackLab sem rodar o banner.

### Changed

- Banner exibe versão a partir de `__version__` (v1.1.0).
- README com seção "Exemplo de saída" para benchmark e wordlist.

## [1.1.0] - 2025-02-26

### Added

- Versão inicial documentada com brute force (single/thread/process), wordlist, hash cracker com detecção automática, benchmark MD5/SHA1/bcrypt, Docker multi-stage e CI com GitHub Actions.

---

[Unreleased]: https://github.com/amchdd/pycracklab/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/amchdd/pycracklab/releases/tag/v1.1.0
