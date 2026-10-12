#!/usr/bin/env bash
# Local numerical runtime installation; no root privileges. Inherited proxy retained.
set -euo pipefail
science_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
tools_dir="$science_dir/.tools"
mkdir -p "$tools_dir" "$science_dir/results"
if [[ $(uname -m) != x86_64 || $(uname -s) != Linux ]]; then
  echo 'Pinned numerical runtimes target Linux x86_64; use JULIA_BIN/OCTAVE_BIN overrides on other platforms.' >&2
  exit 1
fi
if [[ ! -x "$tools_dir/julia-1.11.5/bin/julia" ]]; then
  curl -L --fail --retry 2 --max-time 300 https://julialang-s3.julialang.org/bin/linux/x64/1.11/julia-1.11.5-linux-x86_64.tar.gz -o "$tools_dir/julia.tar.gz"
  printf '%s  %s\n' 723e878c642220cc0251a0e13758c059a389cadc7f01376feaf1ea7388fe8f9c "$tools_dir/julia.tar.gz" | sha256sum --check
  tar -xzf "$tools_dir/julia.tar.gz" -C "$tools_dir"
fi
if [[ ! -x "$tools_dir/octave/bin/octave-cli" ]]; then
  if [[ ! -x "$tools_dir/bin/micromamba" ]]; then
    curl -L --fail --retry 2 --max-time 120 https://conda.anaconda.org/conda-forge/linux-64/micromamba-2.9.0-0.tar.bz2 -o "$tools_dir/micromamba.tar.bz2"
    printf '%s  %s\n' 8761c382127e6363bd9e0a2451aa3ef90d071a79133f736e2f759a3bf13040dd "$tools_dir/micromamba.tar.bz2" | sha256sum --check
    tar -xjf "$tools_dir/micromamba.tar.bz2" -C "$tools_dir" bin/micromamba
  fi
  # Explicit package URLs and hashes pin the successful observed Octave dependency graph.
  "$tools_dir/bin/micromamba" create -y -r "$tools_dir/mamba" -p "$tools_dir/octave" --file "$science_dir/results/octave-conda-explicit.txt"
fi
"$tools_dir/julia-1.11.5/bin/julia" --version
OCTAVE_HOME="$tools_dir/octave" "$tools_dir/octave/bin/octave-cli" --quiet --eval 'assert(rank(eye(3)) == 3); disp(version);'
