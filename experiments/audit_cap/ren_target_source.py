"""Source-bound group loading, without a release or executable fleet entry point.

Reports/schemas must come from the existing approved preflight. This boundary
does not accept arbitrary path lists, repair sources, or make a Gate decision.
"""
import hashlib
from pathlib import Path

from experiments.audit_cap import ren_chronology_gate as prior
from experiments.audit_cap.ren_workbook_reader import workbook_bytes
from experiments.audit_cap.ren_target_group import collect_group
from experiments.audit_cap.ren_target_verify import verify


def source_loader(root, extraction, candidate, reports, schemas):
    root, extraction = Path(root), Path(extraction)
    groups = prior.candidate_groups(reports, schemas)
    if len(groups) != 1 or groups[0][0] != candidate or groups[0][1] != reports:
        raise ValueError('target source candidate/order mismatch')
    rec = prior.fleet.pilot.context.recovery
    rec._no_symlink_components(root, extraction)
    rec._require_dir(extraction, 'target source extraction')
    by_name = {r['member_path']: r for r in reports}
    for member, report in by_name.items():
        scans = report['workbook_scans']
        if len(scans) != 1 or scans[0]['stream_sha256'] != schemas[member]['workbook_sha256']:
            raise ValueError('target source schema binding mismatch')

    def load(member):
        if member not in by_name:
            raise ValueError('unapproved target source')
        report = by_name[member]
        path = extraction / member
        rec._no_symlink_components(root, path)
        info = rec._require_file(path, 'target source input')
        if info.st_nlink != 1 or info.st_size != report['input_bytes'] or info.st_size > 256*1024*1024:
            raise ValueError('target source metadata mismatch')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != report['input_sha256']:
            raise ValueError('target source container mismatch')
        data = workbook_bytes(raw)
        if hashlib.sha256(data).hexdigest() != schemas[member]['workbook_sha256']:
            raise ValueError('target source Workbook mismatch')
        return data
    return list(by_name), load


def collect_source_group(root, extraction, candidate, reports, schemas, allowed):
    members, load = source_loader(root, extraction, candidate, reports, schemas)
    return collect_group(members, schemas, allowed, load)


def verify_source_group(saved, root, extraction, candidate, reports, schemas, allowed):
    """Re-read source containers and reconstruct all saved fields independently.

    This intentionally performs a second input pass; future fleet budget and
    pre-run review must account for it. It is not an in-memory equality check.
    """
    members, load = source_loader(root, extraction, candidate, reports, schemas)
    verify(saved, members, schemas, allowed, load)
