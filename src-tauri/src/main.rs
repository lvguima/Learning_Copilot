#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

#[tauri::command]
fn pick_folder() -> Option<String> {
    rfd::FileDialog::new()
        .pick_folder()
        .map(|path| path.display().to_string())
}

fn backend_addr() -> SocketAddr {
    "127.0.0.1:8008".parse().expect("invalid backend socket")
}

fn backend_is_alive() -> bool {
    TcpStream::connect_timeout(&backend_addr(), Duration::from_millis(250)).is_ok()
}

fn project_root() -> Option<PathBuf> {
    let current = std::env::current_dir().ok()?;
    if current.ends_with("src-tauri") {
        return current.parent().map(Path::to_path_buf);
    }
    Some(current)
}

fn resolve_python_executable(root: &Path) -> String {
    let venv_python = root
        .join("backend")
        .join(".venv")
        .join("Scripts")
        .join("python.exe");
    if venv_python.exists() {
        return venv_python.display().to_string();
    }
    std::env::var("LRC_PYTHON_EXEC").unwrap_or_else(|_| "python".to_string())
}

fn start_sidecar() -> Option<Child> {
    if backend_is_alive() {
        println!("[lrc] backend already running on 127.0.0.1:8008");
        return None;
    }

    let root = project_root()?;
    let backend_dir = root.join("backend");
    if !backend_dir.exists() {
        eprintln!("[lrc] backend directory not found: {}", backend_dir.display());
        return None;
    }

    let python = resolve_python_executable(&root);
    println!(
        "[lrc] starting backend with executable {} in {}",
        python,
        backend_dir.display()
    );

    let mut command = Command::new(&python);
    command
        .current_dir(&backend_dir)
        .arg("-m")
        .arg("uvicorn")
        .arg("local_review_copilot.server:app")
        .arg("--host")
        .arg("127.0.0.1")
        .arg("--port")
        .arg("8008");

    if !cfg!(debug_assertions) {
        command.stdout(Stdio::null()).stderr(Stdio::null());
    }

    match command.spawn() {
        Ok(child) => {
            for _ in 0..40 {
                if backend_is_alive() {
                    println!("[lrc] backend startup detected");
                    break;
                }
                thread::sleep(Duration::from_millis(150));
            }
            Some(child)
        }
        Err(error) => {
            eprintln!("[lrc] failed to start backend: {error}");
            None
        }
    }
}

fn stop_sidecar(state: &Arc<Mutex<Option<Child>>>) {
    if let Ok(mut guard) = state.lock() {
        if let Some(child) = guard.as_mut() {
            let _ = child.kill();
            let _ = child.wait();
            println!("[lrc] backend process stopped");
        }
        *guard = None;
    }
}

fn main() {
    let sidecar = Arc::new(Mutex::new(None::<Child>));
    let setup_sidecar = Arc::clone(&sidecar);
    let shutdown_sidecar = Arc::clone(&sidecar);

    let app = tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![pick_folder])
        .setup(move |_| {
            if let Ok(mut child) = setup_sidecar.lock() {
                *child = start_sidecar();
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to build app");

    app.run(move |_app_handle, event| match event {
        tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit => {
            stop_sidecar(&shutdown_sidecar);
        }
        _ => {}
    });
}

