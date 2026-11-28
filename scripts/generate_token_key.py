"""Local masked Fernet key generation; never print or persist the key."""
import tkinter as tk
from cryptography.fernet import Fernet


def main():
    window=tk.Tk()
    window.title('Scorpions AI — TOKEN_ENCRYPTION_KEY')
    window.geometry('620x230')
    key=Fernet.generate_key().decode()
    message=tk.StringVar(value='A new encryption key is ready in memory.\nCopy it directly into Render TOKEN_ENCRYPTION_KEY.\nKeep it stable and save it in your password manager. It is not saved here.')
    tk.Label(window,textvariable=message,wraplength=580,pady=20).pack()
    field=tk.Entry(window,show='*',width=65)
    field.insert(0,key)
    field.configure(state='readonly')
    field.pack(pady=8)
    def copy():
        window.clipboard_clear()
        window.clipboard_append(key)
        message.set('Copied. Paste into Render, then close this window.\nDo not paste the key into chat or reveal it in screenshots.')
    tk.Button(window,text='Copy encryption key for Render',command=copy).pack(pady=10)
    window.mainloop()


if __name__=='__main__': main()
