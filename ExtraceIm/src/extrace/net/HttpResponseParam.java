package extrace.net;


//HTTPӦ�𷵻ز���

public class HttpResponseParam{
	RETURN_STATUS statusCode;	//״̬��
	String responseClassName;	//���ж��ַ��صĶ������ʱ,���������������
	String responseString;		//��Ӧ��ʵ��JSON�ַ���
	//String responseMessage;		//��Ӧ����Ϣ�ַ���
	public HttpResponseParam(){
		statusCode = RETURN_STATUS.Ok;
		responseClassName = "";
	}

	public enum RETURN_STATUS{
		Ok,
		Saved,
		RequestException,
		ResponseException,
		ServerException,
		ObjectNotFoundException,
		NetworkException,
		Unknown
	}
}
