// 防止 release 模式弹出控制台窗口，勿删
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{convert::Infallible, env::var, error::Error, path::PathBuf};

use pyo3::wrap_pymodule;
use pytauri::standalone::{
    dunce::simplified, PythonInterpreterBuilder, PythonInterpreterEnv, PythonScript,
};
use tauri::utils::platform::resource_dir;

use sse_gui_lib::{ext_mod, tauri_generate_context};

fn main() -> Result<Infallible, Box<dyn Error>> {
    let py_env = if cfg!(dev) {
        // tauri dev 模式：用激活的 venv（读 VIRTUAL_ENV 环境变量）
        let venv_dir = var("VIRTUAL_ENV").map_err(|err| {
            format!(
                "tauri dev 模式请先激活 Python venv，或设 VIRTUAL_ENV 环境变量: {err}",
            )
        })?;
        PythonInterpreterEnv::Venv(PathBuf::from(venv_dir).into())
    } else {
        // 打包模式：用嵌入的 python-build-standalone（放在 resource_dir 下）
        let context = tauri_generate_context();
        let resource_dir = resource_dir(context.package_info(), &tauri::Env::default())
            .map_err(|err| format!("获取 resource_dir 失败: {err}"))?;
        // 去掉 UNC 前缀 \\?\，Python 生态不喜欢它
        let resource_dir = simplified(&resource_dir).to_owned();
        PythonInterpreterEnv::Standalone(resource_dir.into())
    };

    // 等价于 `python -m sse_gui`，即运行 src-tauri/python/sse_gui/__main__.py
    let py_script = PythonScript::Module("sse_gui".into());

    // ext_mod 从内存导出，无需编译成 .pyd 文件
    let builder =
        PythonInterpreterBuilder::new(py_env, py_script, |py| wrap_pymodule!(ext_mod)(py));
    let interpreter = builder.build()?;

    let exit_code = interpreter.run();
    std::process::exit(exit_code);
}
