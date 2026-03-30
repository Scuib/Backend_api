import resend

resend.api_key = "re_BTE5nRNb_PBmLrH2HCfNYjQySink9SB8T"

params: resend.ApiKeys.CreateParams = {
  "name": "Production",
}

resend.ApiKeys.create(params)
