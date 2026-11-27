from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from app.main import TaskIn, plan


@pytest.mark.parametrize('fields', [
    {'priority':'invalid'}, {'status':'invalid'}, {'duration':-1},
    {'duration':0}, {'due_date':'tomorrow'}, {'due_date':'2026-02-30'},
])
def test_invalid_task_fields_rejected(fields):
    with pytest.raises(ValidationError):
        TaskIn(title='Synthetic', **fields)


def test_plan_never_starts_in_past_or_exceeds_window():
    start=datetime(2026,11,27,12,45,tzinfo=timezone.utc)
    tasks=[{'title':str(i),'status':'pending','duration':60} for i in range(3)]
    result=plan(tasks,start=start,hours=2)
    assert result[0]['start']==start.isoformat()
    assert result[1]['status']=='outside_planning_window'
    assert result[2]['status']=='outside_planning_window'
