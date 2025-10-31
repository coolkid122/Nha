from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from luaparser import ast
import os
import uvicorn

class Deobfuscator(ast.ASTVisitor):
    def __init__(self):
        super().__init__()
        self.scopes = [{}]
        self.counter = 0

    def new_name(self):
        self.counter += 1
        return f"v{self.counter}"

    def push_scope(self):
        self.scopes.append({})

    def pop_scope(self):
        self.scopes.pop()

    def visit_Name(self, node):
        for scope in reversed(self.scopes):
            if node.id in scope:
                node.id = scope[node.id]
                break
        self.generic_visit(node)

    def visit_Block(self, node):
        self.push_scope()
        self.generic_visit(node)
        self.pop_scope()

    def visit_Function(self, node):
        if node.name:
            self.visit(node.name)
        self.push_scope()
        for arg in node.args:
            old = arg.id
            new = self.new_name()
            arg.id = new
            self.scopes[-1][old] = new
        self.generic_visit(node.body)
        self.pop_scope()

    def visit_LocalFunction(self, node):
        old = node.name.id
        new = self.new_name()
        node.name.id = new
        self.scopes[-1][old] = new
        self.push_scope()
        for arg in node.args:
            old = arg.id
            new = self.new_name()
            arg.id = new
            self.scopes[-1][old] = new
        self.generic_visit(node.body)
        self.pop_scope()

    def visit_LocalAssign(self, node):
        self.generic_visit(node.values)
        for target in node.targets:
            self.generic_visit(target)
            if isinstance(target, ast.Name):
                old = target.id
                new = self.new_name()
                target.id = new
                self.scopes[-1][old] = new

    def visit_For(self, node):
        self.generic_visit(node.start)
        self.generic_visit(node.stop)
        if node.step:
            self.generic_visit(node.step)
        self.push_scope()
        old = node.target.id
        new = self.new_name()
        node.target.id = new
        self.scopes[-1][old] = new
        self.generic_visit(node.body)
        self.pop_scope()

    def visit_Forin(self, node):
        self.generic_visit(node.iter)
        self.push_scope()
        for target in node.targets:
            old = target.id
            new = self.new_name()
            target.id = new
            self.scopes[-1][old] = new
        self.generic_visit(node.body)
        self.pop_scope()

    def visit_While(self, node):
        self.generic_visit(node.test)
        self.push_scope()
        self.generic_visit(node.body)
        self.pop_scope()

    def visit_Repeat(self, node):
        self.push_scope()
        self.generic_visit(node.body)
        self.generic_visit(node.test)
        self.pop_scope()

    def visit_If(self, node):
        self.generic_visit(node.test)
        self.push_scope()
        self.generic_visit(node.body)
        self.pop_scope()
        for oelseif in node.orelse:
            if hasattr(oelseif, 'test'):
                self.generic_visit(oelseif.test)
            self.push_scope()
            self.generic_visit(oelseif.body)
            self.pop_scope()

    def visit_Do(self, node):
        self.push_scope()
        self.generic_visit(node.body)
        self.pop_scope()

app = FastAPI()

@app.route("/", methods=["GET", "POST"])
async def index(request: Request, input_code: str = Form(None)):
    output_code = ''
    error = None

    if request.method == "POST" and input_code:
        try:
            tree = ast.parse(input_code)
            deobf = Deobfuscator()
            deobf.visit(tree)
            output_code = ast.to_lua_source(tree)
        except Exception as e:
            error = f"Error processing code: {str(e)}"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Luau Deobfuscator</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ padding: 20px; background-color: #f8f9fa; }}
            .container {{ max-width: 1200px; }}
            textarea {{ font-family: monospace; height: 400px; }}
            .btn-submit {{ margin-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="text-center mb-4">Luau Script Deobfuscator</h1>
            <form method="POST">
                <div class="row">
                    <div class="col-md-6">
                        <h3>Input Obfuscated Code</h3>
                        <textarea name="input_code" class="form-control" placeholder="Paste your obfuscated Luau code here...">{input_code or ''}</textarea>
                    </div>
                    <div class="col-md-6">
                        <h3>Deobfuscated Output</h3>
                        <textarea class="form-control" readonly>{output_code}</textarea>
                    </div>
                </div>
                {"<div class='alert alert-danger mt-3'>" + error + "</div>" if error else ''}
                <div class="text-center">
                    <button type="submit" class="btn btn-primary btn-lg btn-submit">Deobfuscate</button>
                </div>
            </form>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
