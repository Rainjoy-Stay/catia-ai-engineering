import ast
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from threading import Event
from time import perf_counter
import unittest


class PairSchedulerTests(unittest.TestCase):
    def scheduler(self, execute, deadline=None, pause_file=None):
        source=Path(__file__).parents[1]/'catia_checker'/'large_single_part.py'
        tree=ast.parse(source.read_text(encoding='utf-8'))
        fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='execute_many')
        scope=dict(workers=2,deadline=deadline,deferred=set(),perf_counter=perf_counter,
                   wait=wait,FIRST_COMPLETED=FIRST_COMPLETED,execute=execute,
                   pause_file=pause_file,emit=lambda event:None,resident=None,
                   initial_workers=2,initial_deadline=deadline)
        # Preserve the production scheduler's nonlocal pause state in its closure.
        wrapper=ast.parse('def factory():\n paused=False\n workers=initial_workers\n deadline=initial_deadline\n worker_pool=None\n return execute_many').body[0]
        wrapper.body.insert(-1,fn)
        module=ast.fix_missing_locations(ast.Module(body=[wrapper],type_ignores=[]))
        exec(compile(module,str(source),'exec'),scope)
        scope['execute_many']=scope['factory']()
        return scope

    def test_free_slot_is_refilled_before_slow_task_finishes(self):
        third=Event()
        def execute(first,second,*args):
            if first=='slow':
                self.assertTrue(third.wait(2),'scheduler retained the batch barrier')
            elif first=='third':third.set()
        scope=self.scheduler(execute)
        with ThreadPoolExecutor(max_workers=2) as pool:
            scope['execute_many'](pool,[('slow','x'),('fast','x'),('third','x')],30,'PRIMARY')
        self.assertTrue(third.is_set())

    def test_expired_budget_defers_without_dispatch(self):
        calls=[]
        scope=self.scheduler(lambda *a:calls.append(a),perf_counter()-1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            scope['execute_many'](pool,[('a','b'),('c','d')],30,'PRIMARY')
        self.assertEqual(calls,[])
        self.assertEqual(scope['deferred'],{('a','b'),('c','d')})

    def test_pause_before_dispatch_preserves_pending_pairs(self):
        from types import SimpleNamespace
        calls=[]
        scope=self.scheduler(lambda *a:calls.append(a),pause_file=SimpleNamespace(exists=lambda:True))
        with ThreadPoolExecutor(max_workers=2) as pool:
            scope['execute_many'](pool,[('a','b'),('c','d')],30,'PRIMARY')
        self.assertEqual(calls,[])
        self.assertEqual(scope['deferred'],{('a','b'),('c','d')})
