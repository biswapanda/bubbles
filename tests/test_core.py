import unittest
from bubbles import *
# import bubbles.iterator

# FIXME: clean this up
import inspect

def default(ctx, left):
    pass

def unary(ctx, left):
    pass

def binary(ctx, left, right):
    pass

class DummyDataObject(DataObject):
    def __init__(self, reps=None, data=None):
        """Creates a dummy data object with bogus representations `reps` and
        arbitrary data `data`"""
        self.reps = reps or []
        self.data = data

    def representations(self):
        return self.reps

class TextObject(DataObject):
    def __init__(self, string):
        self.string = string

    def representations(self):
        return ["rows", "text"]

    def rows(self):
        return iter(self.string)

    def text(self):
        return self.string

class KernelTestCase(unittest.TestCase):
    def test_match(self):
        self.assertTrue(Signature("sql").matches("sql"))
        self.assertTrue(Signature("*").matches("sql"))
        self.assertTrue(Signature("sql[]").matches("sql[]"))
        self.assertTrue(Signature("*[]").matches("sql[]"))

        self.assertFalse(Signature("sql").matches("rows"))
        self.assertFalse(Signature("sql").matches("sql[]"))

    def test_common_reps(self):
        objs = [
                DummyDataObject(["a", "b", "c"]),
                DummyDataObject(["a", "b", "d"]),
                DummyDataObject(["b", "d", "e"])
            ]
        self.assertEqual(["b"], list(common_representations(*objs)))

        objs = [
                DummyDataObject(["a", "b", "c"]),
                DummyDataObject(["a", "b", "d"]),
                DummyDataObject(["d", "d", "e"])
            ]
        self.assertEqual([], list(common_representations(*objs)))

    def test_prototype(self):
        proto = Signature("sql", "sql")
        match = Signature("*", "*")
        self.assertEqual(match, proto.as_prototype())

        proto = Signature("sql[]", "sql")
        match = Signature("*[]", "*")
        self.assertEqual(match, proto.as_prototype())

        proto = Signature("*[]", "*")
        match = Signature("*[]", "*")
        self.assertEqual(match, proto.as_prototype())

    def test_create_op(self):
        def fun(ctx, a, b):
            pass

        self.assertFalse(is_operation(fun))

        op = Operation(fun, Signature("sql", "rows"))

        self.assertEqual("fun", op.name)
        self.assertEqual("sql", op.signature[0])

        op2 = operation("sql", "rows")(fun)

        self.assertEqual("fun", op.name)
        self.assertEqual("sql", op.signature[0])

        self.assertEqual(op.function, op2.function)
        self.assertEqual(op.name, op2.name)
        self.assertEqual(op.signature, op2.signature)
        self.assertEqual(op, op2)

    def test_register(self):
        def func(ctx, obj):
            pass

        c = OperationContext()
        self.assertFalse(c.operations["func"])

        c.add_operation(Operation(func, Signature("sql")))
        self.assertTrue(c.operations["func"])

        c.add_operation(Operation(func, Signature("sql"), name="other"))
        self.assertTrue(c.operations["other"])

        with self.assertRaises(ArgumentError):
            c.add_operation(Operation(func, Signature("sql")))

    def test_register_decorated(self):
        def func(ctx, obj):
            pass

        c = OperationContext()

        op = Operation(func, ["rows"])
        c.add_operation(op)
        self.assertTrue(c.operations["func"])

        with self.assertRaises(ArgumentError):
            c.add_operation(op)

    def test_prototype(self):
        def join(ctx, master, detail, master_key, detail_key):
            pass

        c = OperationContext()

        op = Operation(join, Signature("rows", "rows"))
        c.add_operation(op)

        proto = c.operation_prototype("join")
        self.assertEqual(2, proto.operand_count)
        self.assertSequenceEqual(["master", "detail"], proto.operands)
        self.assertSequenceEqual(["master_key", "detail_key"],
                                 proto.parameters)


    def test_extract_signatures(self):
        obj = DummyDataObject(["rows", "sql"])
        self.assertEqual( [["rows", "sql"]], extract_signatures(obj))

        obj = DummyDataObject(["rows", "sql"])
        extr = extract_signatures([obj])
        self.assertEqual( [["rows[]", "sql[]"]], extr)

    def test_lookup(self):
        c = OperationContext()

        obj_sql = DummyDataObject(["sql"])
        obj_rows = DummyDataObject(["rows"])

        c.add_operation(Operation(unary, signature=Signature("sql")))
        c.add_operation(Operation(default, name="unary",
                                signature=Signature("*")))

        match = c.lookup_operation("unary", obj_sql)
        self.assertEqual(unary, match.function)

        match = c.lookup_operation("unary", obj_rows)
        self.assertEqual(default, match.function)

        with self.assertRaises(OperationError):
            c.lookup_operation("foo", obj_sql)

        with self.assertRaises(OperationError):
            c.lookup_operation("unary", obj_sql, obj_sql)

    def test_lookup_additional_args(self):
        def func(ctx, obj, value):
            pass

        c = OperationContext()
        c.add_operation(Operation(func,
                                signature=Signature("rows")))

        obj = DummyDataObject(["rows"])

        c.o.func(obj, 1)

    def test_comparison(self):
        sig1 = Signature("a", "b", "c")
        sig2 = Signature("a", "b", "c")
        sig3 = Signature("a", "b")

        self.assertTrue(sig1 == sig1)
        self.assertTrue(sig1 == sig2)
        self.assertFalse(sig1 == sig3)

        self.assertTrue(sig1 == ["a", "b", "c"])
        self.assertFalse(sig1 == ["a", "b"])

    def test_delete(self):
        c = OperationContext()
        obj = DummyDataObject(["rows"])

        c.add_operation(Operation(unary, signature=Signature("rows")))
        c.add_operation(Operation(default, name="unary", signature=Signature("*")))

        match = c.lookup_operation("unary", obj)
        self.assertEqual(unary, match.function)

        c.remove_operation("unary", ["rows"])
        match = c.lookup_operation("unary", obj)
        self.assertEqual(default, match.function)

        c.remove_operation("unary")
        with self.assertRaises(OperationError):
            c.lookup_operation("unary", obj)

    def test_running(self):
        def func_text(ctx, obj):
            text = obj.text()
            return list(text.upper())

        def func_rows(ctx, obj):
            rows = obj.rows()
            text = "".join(rows)
            return list(text.upper())

        c = OperationContext()
        c.add_operation(Operation(func_text, name="upper",
                                signature=Signature("text")))
        c.add_operation(Operation(func_rows, name="upper",
                                signature=Signature("rows")))

        obj = TextObject("windchimes")

        result = c.o.upper(obj)
        self.assertEqual(list("WINDCHIMES"), result)
        # func = om.match("upper")

    def test_retry(self):
        @operation("sql", "sql", name="join")
        def join_sql(ctx, l, r):
            if l.data == r.data:
                return "SQL"
            else:
                raise RetryOperation(["sql", "rows"])

        @operation("sql", "rows", name="join")
        def join_iter(ctx, l, r):
            return "ITERATOR"

        @operation("sql", "sql")
        def endless(ctx, l, r):
            raise RetryOperation(["sql", "sql"])

        local = DummyDataObject(["sql", "rows"], "local")
        remote = DummyDataObject(["sql", "rows"], "remote")

        c = OperationContext()
        c.add_operation(join_sql)
        c.add_operation(join_iter)

        result = c.o.join(local, local)
        self.assertEqual(result, "SQL")

        result = c.o.join(local, remote)
        self.assertEqual(result, "ITERATOR")

        c.add_operation(endless)
        with self.assertRaises(RetryError):
            result = c.o.endless(local, local)

    def test_allow_deny_retry(self):
        @operation("sql")
        def swim(ctx, obj):
            raise RetryOperation(["rows"])

        @operation("rows", name="swim")
        def swim_rows(ctx, obj):
            obj.data = "good"
            return obj

        obj = DummyDataObject(["sql", "rows"], "")

        c = OperationContext()
        c.add_operation(swim)
        c.add_operation(swim_rows)

        result = c.op.swim(obj)
        self.assertEqual("good", result.data)

        c.retry_deny = ["swim"]
        c.retry_allow = []
        with self.assertRaises(RetryError):
            c.op.swim(obj)

        c.retry_deny = []
        c.retry_allow = ["swim"]
        result = c.op.swim(obj)
        self.assertEqual("good", result.data)

        c.retry_deny = ["swim"]
        c.retry_allow = ["swim"]
        with self.assertRaises(RetryError):
            c.op.swim(obj)


    def test_retry_nested(self):
        """Test whether failed nested operation fails correctly (Because of
        Issue #4)."""

        @operation("sql")
        def aggregate(ctx, obj, fail):
            if fail:
                raise RetryOperation(["rows"])
            else:
                obj.data += "-SQL-"
            return obj

        @operation("rows", name="aggregate")
        def aggregate_rows(ctx, obj, fail):
            obj.data += "-ROWS-"
            return obj

        @operation("sql")
        def window_aggregate(ctx, obj, fail):
            obj.data += "START"
            ctx.o.aggregate(obj, fail)
            obj.data += "END"

        c = OperationContext()
        c.add_operation(aggregate)
        c.add_operation(aggregate_rows)
        c.add_operation(window_aggregate)

        # Expected order:
        # 1. window_aggregate is called
        # 2. sql aggregate is called, but fails
        # 3. row aggregate is called
        # 4. window aggregate continues

        obj = DummyDataObject(["sql"], "")

        c.o.window_aggregate(obj, fail=True)
        self.assertEqual("START-ROWS-END", obj.data)

        obj.data = ""
        c.o.window_aggregate(obj, fail=False)
        self.assertEqual("START-SQL-END", obj.data)

    def test_priority(self):
        objsql = DummyDataObject(["sql", "rows"])
        objrows = DummyDataObject(["rows", "sql"])

        def fsql(ctx, obj):
            pass
        def frows(ctx, obj):
            pass

        c = OperationContext()
        c.add_operation(Operation(fsql, name="meditate",
                                    signature=Signature("sql")))
        c.add_operation(Operation(frows, name="meditate",
                                    signature=Signature("rows")))

        self.assertEqual(fsql, c.lookup_operation("meditate", objsql).function)
        self.assertEqual(frows, c.lookup_operation("meditate",
                                                            objrows).function)

        # Reverse order of registration, expect the same result
        c = OperationContext()
        c.add_operation(Operation(frows, name="meditate",
                                signature=Signature("rows")))
        c.add_operation(Operation(fsql, name="meditate",
                                signature=Signature("sql")))

        self.assertEqual(fsql, c.lookup_operation("meditate", objsql).function)
        self.assertEqual(frows, c.lookup_operation("meditate",
                                                            objrows).function)

if __name__ == "__main__":
    unittest.main()
