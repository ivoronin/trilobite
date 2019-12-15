# pylint: disable=C0116,C0115,C0114,C0103,R0903
import postpone

def test_postpone_for_1h():
    expected_for_time = 1
    expected_for_unit = 'h'
    expected_for = f'{expected_for_time}{expected_for_unit}'
    command = postpone.parse(f'for {expected_for}')

    assert command.data == "for"
    assert len(command.children) == 1

    postpone_for, = command.children
    assert postpone_for.data == "int"
    assert len(postpone_for.children) == 2

    for_time, for_unit = postpone_for.children
    assert for_time.value == expected_for_time
    assert for_unit.value == expected_for_unit

def test_postpone_for_3600():
    expected_for_time = 3600
    expected_for = f'{expected_for_time}'
    command = postpone.parse(f'for {expected_for}')

    assert command.data == "for"
    assert len(command.children) == 1

    postpone_for, = command.children
    assert postpone_for.data == "int"
    assert len(postpone_for.children) == 1

    for_time, = postpone_for.children
    assert for_time.value == expected_for_time

def test_postpone_for_few_days():
    expected_for_time = 'few days'
    expected_for = f'{expected_for_time}'
    command = postpone.parse(f'for a {expected_for}')

    assert command.data == "for"
    assert len(command.children) == 1

    postpone_for, = command.children
    assert postpone_for.data == "human"
    assert len(postpone_for.children) == 1

    for_time, = postpone_for.children
    assert for_time.value == expected_for_time

def test_postpone_to_next_month():
    expected_to = 'next month'
    command = postpone.parse(f'to the {expected_to}')

    assert command.data == "to"
    assert len(command.children) == 1

    postpone_time, = command.children
    assert postpone_time.data == "human"
    assert len(postpone_time.children) == 1
    postpone_to, = postpone_time.children
    assert postpone_to.value == expected_to

def test_postpone_to_time():
    expected_to = 1571475504
    command = postpone.parse(f'to {expected_to}')

    assert command.data == "to"
    assert len(command.children) == 1

    postpone_time, = command.children
    assert postpone_time.data == "int"
    assert len(postpone_time.children) == 1
    postpone_to, = postpone_time.children
    assert postpone_to.value == expected_to
