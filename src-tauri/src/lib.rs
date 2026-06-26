use pyo3::prelude::*;

/// 生成 Tauri 上下文（读 tauri.conf.json + icons 等）。
pub fn tauri_generate_context() -> tauri::Context {
    tauri::generate_context!()
}

/// PyO3 扩展模块 `ext_mod`：把 pytauri 的 `builder_factory` / `context_factory`
/// 导出到 Python 端。standalone 模式下 Python 通过这个 ext_mod 拿到 Tauri builder。
#[pymodule(gil_used = false)]
#[pyo3(name = "ext_mod")]
pub mod ext_mod {
    use super::*;

    #[pymodule_init]
    fn init(module: &Bound<'_, PyModule>) -> PyResult<()> {
        pytauri::pymodule_export(
            module,
            // 对应 Python 端的 context_factory
            |_args, _kwargs| Ok(tauri_generate_context()),
            // 对应 Python 端的 builder_factory
            |_args, _kwargs| {
                let builder = tauri::Builder::default()
                    .plugin(tauri_plugin_opener::init());
                Ok(builder)
            },
        )
    }
}
