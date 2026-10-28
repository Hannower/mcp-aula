from server import mcp

if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        # 0.0.0.0 permite que os outros serviços da rede Docker acessem o MCP.
        host="0.0.0.0",
        port=8001,
    )
