from fastapi import FastAPI, Request, Form, UploadFile
from fastapi.responses import HTMLResponse
from luaparser import ast
import os
import uvicorn
import re

class Deobfuscator(ast.ASTVisitor):
    def __init__(self):
        super().__init__()
        self.scopes = [{}]
        self.counter = 0

    def new_name(self):
        self.counter += 1
        return f"var{self.counter}"  # Changed to 'var' for better readability

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

def preprocess_luau(code):
    # Simple preprocessing to remove Luau type annotations for compatibility with luaparser
    # Remove single-line comments
    code = re.sub(r'--.*$', '', code, flags=re.MULTILINE)
    # Remove multi-line comments
    code = re.sub(r'\[\[.*?\]\]', '', code, flags=re.DOTALL)
    # Remove type annotations in parameters and returns (basic, may not handle nested types perfectly)
    code = re.sub(r':\s*[\w<>\|\?\[\]\{\}]+', '', code)  # Remove : type
    code = re.sub(r'->\s*[\w<>\|\?\[\]\{\}]+', '', code)  # Remove -> type
    # Remove !strict or other directives
    code = re.sub(r'--!\w+', '', code)
    return code.strip()

app = FastAPI()

@app.route("/", methods=["GET", "POST"])
async def index(request: Request, input_code: str = Form(None), file: UploadFile = None):
    code = ''
    output_code = ''
    error = None

    if request.method == "POST":
        if file:
            try:
                code = (await file.read()).decode('utf-8')
            except:
                error = "Error reading uploaded file."
        elif input_code:
            code = input_code

        if code:
            try:
                code = preprocess_luau(code)
                tree = ast.parse(code)
                deobf = Deobfuscator()
                deobf.visit(tree)
                output_code = ast.to_pretty_str(tree)  # Use to_pretty_str for better formatting if available, else to_lua_source
            except Exception as e:
                error = f"Error processing code: {str(e)}\nNote: For advanced obfuscators like Moonsec v3 or Prometheus, this tool handles basic variable renaming and beautification. For full deobfuscation, consider specialized tools like Prometheus-Deobfuscator on GitHub or manual analysis."

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Advanced Luau Deobfuscator</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/monokai.min.css">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
        <script>hljs.highlightAll();</script>
        <style>
            body {{ padding: 40px; background-color: #1e1e1e; color: #f8f9fa; }}
            .container {{ max-width: 1400px; }}
            textarea, pre {{ font-family: monospace; }}
            .input-area {{ height: 500px; overflow: auto; }}
            .output-area {{ background-color: #2d2d2d; border-radius: 5px; padding: 15px; }}
            .btn-submit {{ margin-top: 20px; }}
            .copy-btn {{ margin-top: 10px; }}
            h1, h3 {{ color: #ffffff; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="text-center mb-5">Advanced Luau Script Deobfuscator</h1>
            <form method="POST" enctype="multipart/form-data">
                <div class="row">
                    <div class="col-md-6">
                        <h3>Input Obfuscated Code</h3>
                        <textarea name="input_code" class="form-control input-area bg-dark text-light" placeholder="Paste your obfuscated Luau code here...">{code}</textarea>
                        <div class="mt-3">
                            <label for="file" class="form-label">Or Upload File</label>
                            <input type="file" name="file" class="form-control bg-dark text-light">
                        </div>
                    </div>
                    <div class="col-md-6">
                        <h3>Deobfuscated Output</h3>
                        <div class="output-area">
                            <pre><code class="language-lua" id="output-code">{output_code}</code></pre>
                        </div>
                        <button type="button" class="btn btn-secondary copy-btn" onclick="copyOutput()">Copy Output</button>
                    </div>
                </div>
                {f"<div class='alert alert-danger mt-4'>{error}</div>" if error else ''}
                <div class="text-center">
                    <button type="submit" class="btn btn-primary btn-lg btn-submit">Deobfuscate</button>
                </div>
            </form>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            function copyOutput() {{
                const code = document.getElementById('output-code').innerText;
                navigator.clipboard.writeText(code).then(() => alert('Copied to clipboard!'));
            }}
            document.addEventListener('DOMContentLoaded', (event) => {{
                hljs.highlightAll();
            }});
        </script>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
