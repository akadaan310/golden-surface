from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path


@dataclass
class Task:
    id: str
    command: list[str]
    depends: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    priority: int = 50
    timeout_s: float = 300
    retries: int = 0
    requires_hardware: bool = False
    validation: str = 'unit-tested'
    evidence_kind: str = 'engineering'
    cwd: str = '.'
    max_rss_mb: int = 4096

    def __post_init__(self):
        if not self.id or not self.command or self.timeout_s <= 0 or not 0 <= self.retries <= 2:
            raise ValueError('Task needs id, command, positive timeout and at most two retries')
        if any(not isinstance(x, str) for x in self.command):
            raise ValueError('Commands are argv arrays, not shell expressions')
        if self.validation not in ['implemented', 'unit-tested', 'simulation-validated',
                                   'hardware-tested', 'cross-device-validated',
                                   'demonstration-ready', 'research-only', 'unsupported']:
            raise ValueError('Unknown validation level')


def fingerprint(root: Path, task: Task) -> str:
    h = hashlib.sha256(json.dumps(asdict(task), sort_keys=True).encode())
    for pattern in sorted(task.inputs):
        paths = sorted(p for p in root.glob(pattern) if p.is_file())
        if not paths:
            h.update(('missing:' + pattern).encode())
        for path in paths:
            if any(x in path.parts for x in ['node_modules', '.git', '__pycache__', '.next', '.venv']):
                continue
            h.update(str(path.relative_to(root)).encode())
            with path.open('rb') as stream:
                while chunk := stream.read(65536):
                    h.update(chunk)
    return h.hexdigest()


def validate_graph(tasks: list[Task]) -> dict[str, Task]:
    table = {t.id: t for t in tasks}
    if len(table) != len(tasks):
        raise ValueError('Duplicate task ids')
    visiting, done = set(), set()

    def visit(id):
        if id not in table:
            raise ValueError('Unknown dependency ' + id)
        if id in visiting:
            raise ValueError('Dependency cycle at ' + id)
        if id in done:
            return
        visiting.add(id)
        for dep in table[id].depends:
            visit(dep)
        visiting.remove(id)
        done.add(id)

    for id in table:
        visit(id)
    return table
