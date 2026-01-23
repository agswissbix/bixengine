import threading
import queue
from playwright.sync_api import sync_playwright

class BrowserManager:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.request_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _worker_loop(self):
        """
        Thread dedicato che gestisce il browser e le richieste di PDF in background. 
        """
        print("BrowserManager: Avvio worker thread...")
        with sync_playwright() as p:
            # Avvio browser una volta sola
            browser = p.chromium.launch(headless=True)
            print("BrowserManager: Browser avviato nel thread.")

            while True:
                task = self.request_queue.get()
                if task is None:
                    # Segnale di stop
                    break
                
                try:
                    # task è una tupla: (html_content, output_path, css_styles, options, result_queue)
                    html_content, output_path, css_styles, options, result_queue = task
                    
                    # Logica generazione PDF
                    context = browser.new_context()
                    page = context.new_page()
                    try:
                        page.set_content(html_content, wait_until="networkidle")
                        
                        if css_styles:
                            page.add_style_tag(content=css_styles)
                        
                        pdf_options = {
                            "path": output_path,
                            "format": "A4",
                            "print_background": True,
                            "scale": 0.75,
                            "margin": {"top": "1cm", "bottom": "1cm", "left": "1cm", "right": "1cm"}
                        }
                        if options:
                            pdf_options.update(options)

                        page.pdf(**pdf_options)
                        result_queue.put({"success": True})
                    except Exception as e:
                        print(f"BrowserManager Error making PDF: {e}")
                        result_queue.put({"success": False, "error": str(e)})
                    finally:
                        page.close()
                        context.close()
                
                except Exception as e:
                    print(f"BrowserManager Worker Error: {e}")
                finally:
                    self.request_queue.task_done()
            
            browser.close()
            print("BrowserManager: Browser chiuso.")

    @classmethod
    def generate_pdf(cls, html_content, output_path, css_styles=None, options=None):
        """
        Metodo pubblico thread-safe per generare un PDF a partire da un file HTML.
        """
        manager = cls.get_instance()
        result_queue = queue.Queue()
        
        # Invia richiesta al worker
        manager.request_queue.put((html_content, output_path, css_styles, options, result_queue))
        
        # Attendi risultato
        result = result_queue.get()
        if not result["success"]:
            raise Exception(result.get("error", "Unknown error in PDF generation"))
        
        return True

    @classmethod
    def close(cls):
        if cls._instance:
            cls._instance.request_queue.put(None)
            cls._instance.worker_thread.join()
            cls._instance = None
